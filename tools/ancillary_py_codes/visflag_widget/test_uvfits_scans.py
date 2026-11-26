"""Regression tests for UVFITS scan identity; inputs are temporary FITS files."""
import tempfile
import unittest
from pathlib import Path

import numpy as np
from astropy.io import fits

from visibility import Visibility


def fixture(path, ids=None, indexed=False):
    names = ["DATE", "BASELINE"]
    values = [[2460000.5, 2460000.5, 2460000.51], [258]*3]
    if ids is not None:
        names.append("SCAN_NUMBER")
        values.append(ids)
    data = fits.GroupData(np.zeros((3,1,1,1,1,4,3)), bitpix=-64, parnames=names, pardata=values)
    primary = fits.GroupsHDU(data)
    primary.header.update(OBJECT="TEST", **{"DATE-OBS":"2023-02-25"}, CTYPE2="COMPLEX",
                          CTYPE3="STOKES", CTYPE4="FREQ", CTYPE5="IF", CRVAL3=-1,
                          CRPIX3=1, CDELT3=-1, CRVAL4=230e9, CDELT4=1e6, CRPIX4=1)
    def table(name, columns):
        return fits.BinTableHDU.from_columns(
            [fits.Column(name=k, format=f, array=a) for k,f,a in columns], name=name)
    hdus = [primary,table("AIPS AN",[("NOSTA","J",[1,2]),("ANNAME","2A",["AA","BB"])]),
            table("AIPS FQ",[(k,"J",[v]) for k,v in
                             [("FRQSEL",1),("IF FREQ",0),("CH WIDTH",1),("SIDEBAND",1)]])]
    if indexed:
        hdus.append(table("AIPS NX",[("START VIS","J",[1,3]),("END VIS","J",[2,3]),
                                     ("SCAN ID","J",[2,20])]))
    fits.HDUList(hdus).writeto(path,overwrite=True)


class ScanIdentity(unittest.TestCase):
    def test_scan_command_uses_embedded_scan_times(self):
        from types import SimpleNamespace
        from app import Review
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root/"test.uvf"
            commands = root/"commands.py"
            commands.write_text("flagdata(vis='test.ms', mode='manual', antenna='AA&BB', scan='20')\n")
            args = SimpleNamespace(vis=path, scan_log=None, scan_gap=60, casa_python=None,
                                   field=None, pdf=None, commands=commands, native_ms=None,
                                   output=root/"approved.py")
            fixture(path)
            with self.assertRaisesRegex(ValueError,"Local time-gap"):
                Review(args)
            fixture(path,[2,2,20])
            review = Review(args)
            state = review.state()
            self.assertEqual(state["scan"],20)
            self.assertIn("00:14:24",state["command"])
            self.assertNotIn("scan=",state["command"])
            review.primary.fits.close()

    def test_metadata_and_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"test.uvf"
            for ids,indexed,expected in [
                    ([2,2,20],False,[2,2,20]),(None,True,[2,2,20]),
                    ([2,2,20],True,[2,2,20]),(None,False,[1,1,2])]:
                fixture(path,ids,indexed)
                ds = Visibility(path, None if expected[0]==1 else path.with_suffix(".missing"))
                np.testing.assert_array_equal(ds.scans,expected)
                self.assertEqual(ds.local_scans,expected[0]==1)
                ds.fits.close()
            for ids,indexed in [([2,2,2.5],False),([2,2,21],True)]:
                fixture(path,ids,indexed)
                with self.assertRaises(ValueError):
                    Visibility(path)
            fixture(path)
            for i,scan in enumerate([3,4]):
                log = path.parent/f"diagnostics_{i}"/"list.obs"
                log.parent.mkdir()
                log.write_text(f"00:00:00.0 - 00:15:00.0 {scan} 0 TEST src\n")
            with self.assertRaisesRegex(ValueError,"different scans"):
                Visibility(path)
            ds = Visibility(path,log)
            np.testing.assert_array_equal(ds.scans,[4,4,4])
            ds.fits.close()


if __name__ == "__main__":
    unittest.main()
