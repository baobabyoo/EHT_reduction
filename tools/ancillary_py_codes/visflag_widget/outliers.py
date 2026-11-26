"""Trace clicked markers back to CASA time, channel and hand selections."""
from collections import defaultdict
import secrets

import numpy as np

from selections import axes, command, utc
from visibility import HANDS


class PickView:
    """Keep coordinates and sample IDs for one frozen rendering on the server."""

    def __init__(self):
        self.token = secrets.token_urlsafe(16)
        self.series = defaultdict(list)
        self.picks = {}

    def add(self, row, column, hand, x, z, identify):
        self.series[row, column].append((hand, x, z, identify))

    def nearest(self, panel, x, y, width, height):
        g = self.geometry[panel]
        xlim, ylim = g["x"], g["y"]
        dx = width * g["box"][2] / (xlim[1] - xlim[0])
        dy = height * g["box"][3] / (ylim[1] - ylim[0])
        row, col = panel // 4, panel // 2 % 2
        best = float("inf")
        answer = None
        for hand, xs, zs, identify in reversed(self.series[row, col]):
            ys = np.abs(zs) if g["amplitude"] else np.angle(zs, deg=True)
            within = (xs >= xlim[0]) & (xs <= xlim[1]) & (ys >= ylim[0]) & (ys <= ylim[1])
            ids = np.flatnonzero(within)
            if not len(ids):
                continue
            distance = ((xs[ids] - x) * dx) ** 2 + ((ys[ids] - y) * dy) ** 2
            k = distance.argmin()
            if distance[k] < best:
                best = distance[k]
                i = ids[k]
                times, channels = identify(i)
                key = (row, col, tuple(times), tuple(channels), (hand,))
                answer = key, float(xs[i]), float(ys[i])
        if answer is None:
            raise ValueError("No visible sample in this panel")
        key, px, py = answer
        self.picks.setdefault(key, len(self.picks))
        return dict(id=self.picks[key], hand=key[-1][0], x=px, y=py)

    def commands(self, d, base, ids):
        chosen = set(ids)
        if not chosen.issubset(self.picks.values()):
            raise ValueError("Pick list has changed. Start picking again.")
        groups = defaultdict(list)
        for (row, col, t, f, h), i in self.picks.items():
            if i in chosen:
                groups[row, col].append((t, f, h))
        calls = []
        for (row, col), rectangles in groups.items():
            # Union along ONE dimension only when both other selectors agree.
            # This cannot introduce any unpicked time/channel/hand combinations.
            previous = None
            while previous != len(rectangles):
                previous = len(rectangles)
                for axis in (1, 0, 2):
                    merged = defaultdict(set)
                    for rect in rectangles:
                        merged[rect[:axis] + rect[axis + 1 :]].update(rect[axis])
                    rectangles = [k[:axis] + (tuple(sorted(v)),) + k[axis:] for k, v in merged.items()]
            for ts, fs, hands in rectangles:
                full_band = (row, col) == (0, 0) and len(fs) == len(d["f"])
                k = dict(
                    base,
                    timerange=time_ranges(d["t"], ts),
                    spw="" if full_band else spectral_ranges(d, fs),
                    correlation=",".join(h for h in HANDS if h in hands),
                )
                selection = axes(k, d, int(base.get("scan") or 0), base["antenna"], base["field"])
                for actual, expected in zip(selection, (ts, fs, [HANDS.index(h) for h in hands])):
                    if not np.array_equal(np.flatnonzero(actual), np.sort(expected)):
                        raise ValueError(
                            "CASA coordinates cannot uniquely select this pick on this baseline"
                        )
                calls.append(command(k))
        return calls


def runs(ids):
    a = np.unique(ids)
    return np.split(a, np.flatnonzero(np.diff(a) > 1) + 1)


def time_ranges(times, indices):
    all_times = np.unique(times)
    positions = np.searchsorted(all_times, np.unique(times[list(indices)]))
    parts = []
    for run in runs(positions):
        lo, hi = run[0], run[-1]
        # Avoid UTC formatting at the edge of an integration, without reaching a neighbour.
        left = min(0.001, (all_times[lo] - all_times[lo - 1]) / 3) if lo else 0.00005
        right = (
            min(0.001, (all_times[hi + 1] - all_times[hi]) / 3) if hi + 1 < len(all_times) else 0.00005
        )
        parts.append(utc(all_times[lo] - left) + "~" + utc(all_times[hi] + right))
    return ",".join(parts)


def spectral_ranges(d, indices):
    ix = np.asarray(indices)
    parts = []
    for spw in np.unique(d["spw"][ix]):
        channels = d["ch"][ix[d["spw"][ix] == spw]]
        chunks = [str(g[0]) if len(g) == 1 else f"{g[0]}~{g[-1]}" for g in runs(channels)]
        # Explicit IDs remain exact even in a sparse spectral window.
        parts.append(f"{spw}:" + ";".join(chunks))
    return ",".join(parts)
