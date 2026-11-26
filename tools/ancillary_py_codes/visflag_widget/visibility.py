"""Read a single-source random-groups UVFITS or a CASA Measurement Set."""
from pathlib import Path
import re
import subprocess
import tempfile

import numpy as np
from astropy.io import fits
from astropy.time import Time

HANDS = ["RR", "LL", "RL", "LR"]
COLORS = dict(RR="#EE2C2C", RL="#2E8B57", LR="#0000FF", LL="#314F4F")


class Visibility:
    def __init__(self, path, log=None, gap=60, casa=None, field=None):
        self.path = Path(path).resolve()
        self.is_ms = self.path.is_dir()
        self.casa = casa
        self.target = str(self.path) if self.is_ms else str(self.path.with_suffix(".ms"))
        if self.is_ms:
            meta = self.ms_read("index", field or "")
            self.field = str(meta["field"])
            self.antenna_ids = {str(name): i for i, name in enumerate(meta["antennas"])}
            self.bounds = {int(i): (lo, hi) for i, lo, hi in meta["bounds"]}
            self.scans = meta["scans"]
            self.pairs = meta["pairs"]
            return
        self.fits = fits.open(self.path, memmap=True)
        h = self.fits[0]
        g = h.data
        self.field = h.header["OBJECT"].strip()
        if field and field != self.field:
            raise ValueError("Field does not match UVFITS OBJECT")
        if any(
            not h.header.get(f"CTYPE{i}", "").startswith(axis)
            for i, axis in [(2, "COMPLEX"), (3, "STOKES"), (4, "FREQ"), (5, "IF")]
        ) or g.data.shape[1:3] != (1, 1):
            raise ValueError("Expected standard AIPS random-groups UVFITS axes")
        for axis in ("SOURCE", "FREQSEL"):
            if axis in g.parnames and len(np.unique(g.par(axis))) != 1:
                raise ValueError("Export one source and one frequency setup per UVFITS file")
        self.time = Time(g.par("DATE"), format="jd").unix
        ant = self.fits["AIPS AN"].data
        stations = dict(zip(ant["NOSTA"], (a.strip() for a in ant["ANNAME"])))
        self.antenna_ids = {name: int(number) for number, name in stations.items()}
        code = g.par("BASELINE").astype(int)

        def pair(c):
            a, b = divmod(c - 65536, 2048) if c >= 65536 else divmod(c, 256)
            return "" if a == b else stations[a] + "&" + stations[b]

        self.pairs = np.array([pair(c) for c in np.unique(code)])[np.unique(code, return_inverse=True)[1]]
        self.scans = np.full(len(code), -1)
        if log:
            day = h.header["DATE-OBS"][:10]
            pat = (
                r"(\d\d:\d\d:\d\d\.\d+)\s+-\s+(\d\d:\d\d:\d\d\.\d+)\s+(\d+)\s+\d+\s+"
                + re.escape(self.field)
                + r"\s"
            )
            for a, b, s in re.findall(pat, Path(log).read_text()):
                t = Time([day + "T" + a, day + "T" + b]).unix
                use = (self.time >= t[0] - 0.00005) & (self.time <= t[1] + 0.010)
                if (self.scans[use] != -1).any():
                    raise ValueError("Overlapping scan intervals")
                self.scans[use] = int(s)
            if (self.scans < 0).any():
                raise ValueError("Observing log does not cover this export")
        else:
            times = np.unique(self.time)
            self.scans = np.searchsorted(times[1:][np.diff(times) > gap], self.time, side="right") + 1
        hdr = h.header
        codes = hdr["CRVAL3"] + (1 + np.arange(hdr["NAXIS3"]) - hdr["CRPIX3"]) * hdr["CDELT3"]
        self.order = [(i, int(-c - 1)) for i, c in enumerate(codes) if c in (-1, -2, -3, -4)]
        if not self.order:
            raise ValueError("Expected circular correlation products")
        fqrows = self.fits["AIPS FQ"].data
        selector = g.par("FREQSEL")[0] if "FREQSEL" in g.parnames else fqrows["FRQSEL"][0]
        matching = fqrows[fqrows["FRQSEL"] == selector]
        if len(matching) != 1:
            raise ValueError("No unique AIPS FQ row for visibility data")
        fq = matching[0]
        offsets = np.atleast_1d(fq["IF FREQ"])
        width = np.atleast_1d(fq["CH WIDTH"])
        side = np.atleast_1d(fq["SIDEBAND"])
        signed = np.where(side == 0, np.sign(hdr["CDELT4"]), np.sign(side))
        widths = np.where(width != 0, np.abs(width), abs(hdr["CDELT4"])) * signed
        if hdr["NAXIS4"] > 1 and (np.any(widths == 0) or not np.isfinite(widths).all()):
            raise ValueError("Cannot determine individual channel frequencies")
        channels = np.arange(hdr["NAXIS4"])
        self.freq = (
            (hdr["CRVAL4"] + offsets[:, None] + widths[:, None] * (channels + 1 - hdr["CRPIX4"])) / 1e9
        ).ravel()
        self.spw = np.repeat(np.arange(len(offsets)), len(channels))
        self.chan = np.tile(channels, len(offsets))

    def ms_read(self, *args):
        if not self.casa:
            raise ValueError("Set --casa-python to CASA’s Python executable")
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "data.npz"
            run = subprocess.run(
                [
                    self.casa,
                    str(Path(__file__).with_name("ms_reader.py")),
                    str(self.path),
                    str(output),
                    *map(str, args),
                ],
                cwd=tmp,
                capture_output=True,
                text=True,
            )
            if run.returncode:
                raise ValueError(run.stderr[-1800:])
            with np.load(output) as f:
                return dict(f)

    def baselines(self, scan):
        return sorted(set(self.pairs[self.scans == int(scan)]) - {""})

    def read(self, scan, baseline):
        if self.is_ms:
            return self.ms_read("read", self.field, scan, baseline)
        mask = (self.scans == int(scan)) & (self.pairs == baseline)
        raw = self.fits[0].data.data[mask, 0, 0]
        raw = raw.reshape(len(raw), len(self.freq), raw.shape[-2], 3)
        v = np.zeros((*raw.shape[:2], 4), np.complex64)
        w = np.zeros(v.shape, np.float32)
        for i, j in self.order:
            re_, im, wt = raw[:, :, i, :].transpose(2, 0, 1)
            good = np.isfinite(raw[:, :, i, :]).all(-1) & (wt > 0)
            v[:, :, j] = np.where(good, re_ + 1j * im, 0)
            w[:, :, j] = np.where(good, wt, 0)
        return dict(t=self.time[mask], f=self.freq, spw=self.spw, ch=self.chan, v=v, w=w)
