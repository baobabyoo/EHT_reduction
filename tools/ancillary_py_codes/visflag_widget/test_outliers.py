"""Regression checks for exact picks, spectral coordinates, and explicit reset."""
import tempfile
import unittest
from pathlib import Path

import numpy as np

from charts import draw
from outliers import PickView
from selections import Journal, axes, parse
from visibility import HANDS


class OutlierTests(unittest.TestCase):
    def setUp(self):
        self.w = np.ones((5, 4, 4), dtype=float)
        z = np.arange(1, 81).reshape(self.w.shape) + 1j
        self.d = dict(
            t=1700000000.0 + np.arange(5),
            f=np.array([221.03, 221.02, 221.01, 221.00]),
            spw=np.zeros(4, int),
            ch=np.arange(4),
            v=z,
        )
        self.base = dict(vis="test.ms", mode="manual", antenna="A&B", scan="1", field="M87")
        self.view = PickView()
        draw(self.d, self.w, self.w < 0, dict(seconds=2, channels=2), self.view)

    def mask(self, calls):
        result = np.zeros_like(self.w, bool)
        for c in calls:
            result[np.ix_(*axes(parse(c), self.d, 1, "A&B", "M87"))] = True
        return result

    def native(self, t, f, panel=6, hand="RR"):
        # Panel numbering is time average, time native, frequency average, frequency native;
        # each consists of amplitude then phase.
        x = self.d["f"][f] if panel >= 4 else self.d["t"][t] - self.d["t"][0]
        z = self.d["v"][t, f, HANDS.index(hand)]
        return self.view.nearest(panel, x, abs(z), 1200, 800)["id"]

    def test_native_diagonal(self):
        ids = [self.native(0, 0), self.native(2, 2), self.native(0, 0)]
        calls = self.view.commands(self.d, self.base, ids)
        expected = np.zeros_like(self.w, bool)
        expected[0, 0, 0] = expected[2, 2, 0] = True
        self.assertEqual(len(calls), 2)
        np.testing.assert_array_equal(self.mask(calls), expected)

    def test_separated_times_same_channel(self):
        ids = [self.native(t, 1) for t in [0, 3]]
        calls = self.view.commands(self.d, self.base, ids)
        self.assertEqual(len(calls), 1)
        expected = np.zeros_like(self.w, bool)
        expected[[0, 3], 1, 0] = True
        np.testing.assert_array_equal(self.mask(calls), expected)

    def test_averages_both_domains(self):
        z = self.d["v"][:, :, 0]
        a = self.view.nearest(0, 0.5, abs(z[:2].mean()), 1200, 800)
        b = self.view.nearest(4, self.d["f"][2:].mean(), abs(z[:, 2:].mean()), 1200, 800)
        calls = self.view.commands(self.d, self.base, [a["id"], b["id"]])
        self.assertEqual(len(calls), 2)
        expected = np.zeros_like(self.w, bool)
        expected[:2, :, 0] = True
        expected[:, 2:, 0] = True
        np.testing.assert_array_equal(self.mask(calls), expected)

    def test_native_channel_coordinates_and_mixed_resolution(self):
        _, xs, _, _ = self.view.series[1, 1][0]
        np.testing.assert_array_equal(xs, np.tile(self.d["f"], 5))
        a = self.view.nearest(0, 0.5, abs(self.d["v"][:2, :, 0].mean()), 1200, 800)
        b = self.native(3, 1, 2, "LL")
        calls = self.view.commands(self.d, self.base, [a["id"], b])
        self.assertEqual(len(calls), 2)
        expected = np.zeros_like(self.w, bool)
        expected[:2, :, 0] = True
        expected[3, 1, 1] = True
        np.testing.assert_array_equal(self.mask(calls), expected)

    def test_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "flags.py"
            j = Journal(path, {"session": 1})
            j.add(dict(items=[dict(k=self.base, reason="test")]))
            j.lock.close()
            j = Journal(path, {"session": 1})
            self.assertEqual(len(j.data["steps"]), 1)
            j.lock.close()
            j = Journal(path, {"session": 2}, overwrite=True)
            self.assertEqual(j.data["steps"], [])
            self.assertEqual(path.read_text(), "")
            j.lock.close()


if __name__ == "__main__":
    unittest.main()
