"""Plot one reviewed baseline/scan from a single-source, single-channel-per-IF CASA UVFITS.

Usage (from inspection/):
  python visibility_preview.py ../M87_calibrated.uvf NN_PV_scan2_review.json M87_visibility_preview.pdf

Requires Python 3.9+, astropy, numpy and matplotlib. For a new selection copy the
JSON, change the identifiers and UTC scan boundaries from the observation log,
and discard or replace the previous selection's highlights, notes and commands.
Commands are printed only. FITS baseline order is retained; request the stored
station order. Times are seconds from start_utc. IF indices are zero-based.
"""
import argparse
import json
import textwrap
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import to_rgba
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib.ticker import MaxNLocator, FormatStrFormatter
import numpy as np
from astropy.io import fits
from astropy.time import Time
from diagnostic_spectrum import read_channel_spectrum

POL_COLORS = {"RR": "#EE2C2C", "RL": "#2E8B57", "LR": "#0000FF", "LL": "#314F4F"}
DOT_STYLE = dict(marker="o", linestyle="none", markeredgewidth=0)
INK = "#172E3A"
MUTED = "#48616E"


def read_selection(path, review):
    start = Time(review["start_utc"], scale="utc")
    duration = (Time(review["end_utc"], scale="utc") - start).sec
    with fits.open(path, memmap=True) as hdus:
        header, groups = hdus[0].header, hdus[0].data
        axes = [header[f"CTYPE{i}"].strip() for i in range(2, 8)]
        if axes != ["COMPLEX", "STOKES", "FREQ", "IF", "RA", "DEC"] or any(
                header[f"NAXIS{i}"] != 1 for i in (4, 6, 7)):
            raise ValueError("Expected CASA UVFITS with one channel per IF and one sky position")
        if path.name != review["input"] or header["OBJECT"].strip() != review["source"]:
            raise ValueError("Review and input identifiers disagree")
        an = hdus["AIPS AN"].data
        names = {name.strip(): int(n) for name, n in zip(an["ANNAME"], an["NOSTA"])}
        a, b = [names[name] for name in review["baseline"]]
        if not (0 < a < 256 and 0 < b < 256 and a != b):
            raise ValueError("Expected distinct station IDs below 256")
        seconds = (groups.par("DATE") - start.jd) * 86400.0
        mask = (groups.par("BASELINE") == 256*a+b) & (seconds >= 0) & (seconds < duration)
        if not mask.any():
            raise ValueError("No records for this baseline order and UTC interval")
        setup = np.unique(groups.par("FREQSEL")[mask])
        fq = hdus["AIPS FQ"].data
        if len(setup) != 1 or (fq["FRQSEL"] == setup[0]).sum() != 1:
            raise ValueError("Expected one frequency setup")
        offset = fq["IF FREQ"][fq["FRQSEL"] == setup[0]][0]
        freq = (header["CRVAL4"] + (1-header["CRPIX4"])*header["CDELT4"] + offset) / 1e9
        stokes = header["CRVAL3"] + (np.arange(header["NAXIS3"])+1-header["CRPIX3"])*header["CDELT3"]
        lookup = {-1: "RR", -2: "LL", -3: "RL", -4: "LR"}
        pols = [lookup[s] for s in stokes]
        if set(pols) != set(POL_COLORS):
            raise ValueError("Expected four circular correlation products")
        data = groups.data[mask, 0, 0, :, 0, :, :].astype(float)
        unit = header.get("BUNIT", "unspecified").strip()
    vis = data[..., 0] + 1j*data[..., 1]
    w = data[..., 2]
    good = np.isfinite(vis) & np.isfinite(w) & (w > 0)
    return (seconds[mask], duration, freq, pols, np.where(good, vis, 0),
            np.where(good, w, 0), unit)


def average(vis, weights, axes):
    total = weights.sum(axis=axes)
    numerator = (vis*weights).sum(axis=axes)
    return np.divide(numerator, total, out=np.full(total.shape, np.nan+1j*np.nan), where=total > 0)


def plot_pair(fig, cell, title, x, z, pols, xlabel, review, frequency=False, native=False):
    grid = cell.subgridspec(2, 1, hspace=.09)
    upper = fig.add_subplot(grid[0])
    lower = fig.add_subplot(grid[1], sharex=upper)
    upper.set_title(title, loc="left", fontsize=10, fontweight="bold", pad=5)
    if native:
        # Interleave hands so the last polarization drawn cannot mask the others.
        ti, fi, pi = np.nonzero(np.isfinite(z))
        order = np.random.default_rng(0).permutation(len(ti))
        ti, fi, pi = ti[order], fi[order], pi[order]
        horizontal = x[fi if frequency else ti]
        colors = np.array([to_rgba(POL_COLORS[p]) for p in pols])[pi]
        samples = z[ti, fi, pi]
        for ax, y in [(upper, abs(samples)*review["amplitude_scale"]), (lower, np.angle(samples, deg=True))]:
            ax.scatter(horizontal, y, s=.48, c=colors, marker="o", linewidths=0,
                       alpha=.54, rasterized=True, zorder=3)
    else:
        for name, color in POL_COLORS.items():
            col = z[:, pols.index(name)]
            for ax, y in [(upper, abs(col)*review["amplitude_scale"]), (lower, np.angle(col, deg=True))]:
                ax.plot(x, y, color=color, markersize=2.1, **DOT_STYLE)
    upper.tick_params(axis="x", labelbottom=False)
    upper.set_ylabel("Amplitude")
    lower.set_ylabel("Phase (°)")
    lower.set_xlabel(xlabel, labelpad=2)
    lower.set_ylim(-191, 191)
    lower.set_yticks([-180, 0, 180])
    upper.set_ylim(bottom=0)
    upper.yaxis.set_major_locator(MaxNLocator(4, min_n_ticks=3))
    for ax in (upper, lower):
        ax.grid(axis="y", color="#DBE2E6", linewidth=.45)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(length=2.4, pad=2)
    if frequency:
        lower.xaxis.set_major_formatter(FormatStrFormatter("%.1f"))
        lower.xaxis.set_major_locator(MaxNLocator(5))
        for item in review["spectral_marks"]:
            i = item["if"]
            if native:
                for ax in (upper, lower):
                    ax.axvline(x[i], color=INK, linestyle=":", lw=.65, zorder=1)
                upper.annotate(item["label"], (x[i], .98), xycoords=("data", "axes fraction"),
                               xytext=(-4, 0), textcoords="offset points", ha="right", va="top",
                               fontsize=7, weight="bold", bbox=dict(fc="white", ec="none", pad=.5))
                continue
            for name in item["pols"]:
                col = z[i, pols.index(name)]
                for ax, y in [(upper, abs(col)*review["amplitude_scale"]), (lower, np.angle(col, deg=True))]:
                    ax.scatter(x[i], y, marker="o", s=46, facecolors="none",
                               edgecolors=INK, linewidths=.75, zorder=5)
            upper.annotate(item["label"], (x[i], max(abs(z[i,pols.index(p)]) for p in item["pols"])*review["amplitude_scale"]),
                           xytext=(-8, -1), textcoords="offset points", ha="right", va="center",
                           fontsize=7, fontweight="bold", bbox=dict(fc="white", ec="none", pad=.3))
    else:
        lower.set_xlim(0,review["duration_for_plot"])
        for left, right in review["time_marks"]:
            for ax in (upper, lower):
                ax.axvspan(left, right, color="#F7DEAE", alpha=.72, lw=0, zorder=0)


def plot_channel_pair(fig, cell, title, data, pols, review):
    freq, amplitude, phase = data
    grid = cell.subgridspec(2, 1, hspace=.13)
    top = fig.add_subplot(grid[0])
    bottom = fig.add_subplot(grid[1], sharex=top)
    top.set_title(title, loc="left", fontsize=10, weight="bold")
    for label, color in POL_COLORS.items():
        p = pols.index(label)
        for ax, y in [(top, amplitude[:,p]*1000), (bottom, phase[:,p])]:
            ax.plot(freq, y, color=color, markersize=.85, **DOT_STYLE)
    rr = pols.index("RR")
    count = review["channel_diagnostic"]["channels_per_if"]
    for mark in review["spectral_marks"]:
        section = freq[mark["if"]*count:(mark["if"]+1)*count]
        for ax in (top, bottom):
            ax.axvspan(section[0], section[-1], color="#E7EEF3", lw=0, zorder=0)
    for spw, chan in review["channel_diagnostic"]["marked_channels"]:
        i = spw * review["channel_diagnostic"]["channels_per_if"] + chan
        y = amplitude[i,rr] * 1000
        top.scatter(freq[i], y, s=24, facecolor="none", edgecolor=INK, linewidth=.65, zorder=4)
    for ax in (top,bottom):
        ax.grid(axis="y", color="#DBE2E6", linewidth=.45)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(length=2.4, pad=2)
    top.set_ylim(0, np.nanmax(amplitude)*1000*1.20)
    top.tick_params(axis="x",labelbottom=False)
    top.set_ylabel("Amp. (mJy)")
    bottom.set_ylim(-191,191)
    bottom.set_yticks([-180,0,180])
    bottom.set_ylabel("Phase (°)")
    bottom.set_xlabel("Frequency (GHz)",labelpad=2)
    bottom.xaxis.set_major_locator(MaxNLocator(5))
    bottom.xaxis.set_major_formatter(FormatStrFormatter("%.1f"))


def draw_report(path, review, output):
    sec, duration, freq, pols, vis, weights, unit = read_selection(path, review)
    step = review["time_bin_s"]
    edges = np.arange(int(np.ceil(duration / step - 1e-8)) + 1)*step
    values = np.stack([average(vis[(sec>=a)&(sec<b)], weights[(sec>=a)&(sec<b)], (0,1))
                       for a,b in zip(edges[:-1], edges[1:])])
    spectrum = average(vis, weights, 0)
    diagnostic = review.get("channel_diagnostic")
    channels = read_channel_spectrum(path.parent, review, freq, pols) if diagnostic else None
    review["duration_for_plot"] = round(duration, 3)
    baseline = "–".join(review["baseline"])
    title = f"{baseline}  ·  Scan {review['scan']}"
    stamp = datetime.now(ZoneInfo("Asia/Taipei")).strftime("%Y-%m-%d %H:%M %Z (UTC+8)")
    plt.rcParams.update({"font.size":8, "axes.labelsize":8, "xtick.labelsize":7, "ytick.labelsize":7,
                         "text.color":INK, "axes.labelcolor":INK, "axes.edgecolor":"#80949B",
                         "axes.linewidth":.65, "pdf.fonttype":42})
    with PdfPages(output) as pdf:
        def page(heading, number, subtitle):
            fig = plt.figure(figsize=(11.7, 13))
            fig.text(.053,.956,heading,fontsize=22,weight="bold")
            fig.text(.053,.931,subtitle,fontsize=10,color=MUTED)
            fig.add_artist(Line2D([.053,.963],[.914,.914], transform=fig.transFigure,color="#AFBFC5",lw=.8))
            fig.text(.053,.024,f"{review['model']}   ·   {stamp}",fontsize=8,color=MUTED)
            fig.text(.96,.024,str(number),fontsize=9,ha="right",color=MUTED)
            return fig
        native_vis = np.where(weights > 0, vis, complex(np.nan, np.nan))
        valid = int((weights > 0).sum())
        cadence = np.median(np.diff(np.unique(sec)))
        for native in (False, True):
            fine = native and channels is not None
            view = "integrations and frequency channels" if fine else ("individual integrations" if native else "weighted averages")
            fig = page(f"{review['source']} visibility preview · {view}", 2 if native else 1,
                       f"{path.name}    /    {review['start_utc'][:10]}    /    {title}" +
                       (f"    /    Frequency: {Path(diagnostic['file']).name}, p. {diagnostic['page']}" if fine else ""))
            handles = [Line2D([], [], color=color, markersize=4, label=name, **DOT_STYLE)
                       for name, color in POL_COLORS.items()]
            fig.legend(handles=handles,loc="center left",bbox_to_anchor=(.049,.894),ncol=4,
                       frameon=False,columnspacing=1.1,handletextpad=.25)
            marks = "Dotted lines" if native else "Rings"
            fig.text(.34,.889,"Amber: low coherence     Pale blue: IFs A and B     Rings: narrow RR/LL peaks" if fine
                     else f"Amber band   low coherent amplitude      •      {marks}   spectral features A and B",fontsize=9)
            grid = fig.add_gridspec(4,3,left=.093,right=.965,top=.848,bottom=.095,hspace=.61,wspace=.40)
            plot_pair(fig,grid[0,0],title+"   /   Time",sec if native else (edges[:-1]+edges[1:])/2,
                      native_vis if native else values,pols,f"Seconds from {review['start_utc'][11:19]} UTC",review,native=native)
            if fine:
                plot_channel_pair(fig,grid[1,0],title+"   /   Frequency",channels,pols,review)
            else:
                plot_pair(fig,grid[1,0],title+"   /   Frequency",freq,native_vis if native else spectrum,
                          pols,"Frequency (GHz)",review,frequency=True,native=native)
            for r in range(4):
                for c in range(3):
                    if r<2 and c==0:
                        continue
                    box=grid[r,c].get_position(fig)
                    fig.add_artist(Rectangle((box.x0,box.y0),box.width,box.height,transform=fig.transFigure,
                                             fill=False,edgecolor="#DBE2E5",linewidth=.6,linestyle=(0,(3,4))))
            caption = (f"{valid:,} valid samples per panel. One dot per integration (≈{cadence:.1f} s), IF and polarization."
                       if native else f"Time: {step:g} s, all IFs.  Frequency: full scan, one point per IF.")
            if fine:
                fig.text(.053,.052,f"Time: {cadence:.1f} s integrations, |V| × {review['amplitude_scale']:g} ({unit}).   "
                         f"Frequency: {len(channels[0]):,} channels per hand at {diagnostic['spacing_mhz']:g} MHz spacing; amplitude follows the diagnostic’s Jy label.",fontsize=9)
            else:
                fig.text(.053,.052,f"Amplitude = |V| × {review['amplitude_scale']:g} (FITS unit: {unit}).  "+caption,fontsize=9)
            pdf.savefig(fig, dpi=450); plt.close(fig)
        fig = page("Inspection notes and CASA selections",3,f"{path.name}    /    {title}    /    {review['start_utc'][11:19]}–{review['end_utc'][11:19]} UTC")
        y=.875
        def block(label, body):
            nonlocal y
            fig.text(.053,y,label,weight="bold",fontsize=12); y-=.019
            wrapped=textwrap.wrap(body,111)
            fig.text(.053,y,"\n".join(wrapped),va="top",fontsize=10,linespacing=1.32)
            y-=.0143*len(wrapped)+.022
        block("Selection and averaging", f"Original scan ID from {review['scan_log']}. "
              f"{len(sec)} integrations; {len(freq)} IFs, four correlations. "
              f"{valid:,} of {weights.size:,} complex samples have finite values and positive weights. "
              "Page 1 shows UVFITS complex means. Page 2 shows individual UVFITS integrations in time. "
              f"The header gives BUNIT={unit}; the absolute flux scale in Jy is unverified.")
        for item in review["notes"]:
            block(item["title"],item["body"])
        if diagnostic:
            block("Channel-resolved frequency diagnostic",diagnostic["description"])
            pdf.savefig(fig); plt.close(fig)
            fig = page("Proposed CASA flag commands",4,f"{path.name}    /    {title}")
            y=.875
        block("CASA flagging candidates", review["command_note"])
        for command in review["commands"]:
            fig.text(.068,y,command,va="top",family="monospace",fontsize=9.3,linespacing=1.28)
            y-=.014*len(command.splitlines())+.016
        if diagnostic:
            block("Original channelized Measurement Set", diagnostic["command_note"])
            for command in diagnostic["commands"]:
                fig.text(.068,y,command,va="top",family="monospace",fontsize=9.3,linespacing=1.28)
                y-=.014*len(command.splitlines())+.016
        if y < .035:
            raise ValueError("Review notes exceed the page. Shorten them or paginate.")
        pdf.savefig(fig); plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    for name in ("uvfits","review","pdf"):
        parser.add_argument(name,type=Path)
    args=parser.parse_args()
    draw_report(args.uvfits,json.loads(args.review.read_text()),args.pdf)
