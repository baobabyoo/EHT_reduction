"""Four matched views of the same visibility cells."""
import base64
import io
import numpy as np
from matplotlib.figure import Figure
from matplotlib.ticker import ScalarFormatter
from matplotlib.backends.backend_agg import FigureCanvasAgg
from visibility import HANDS, COLORS
from selections import frequencies, utc


def draw(d, w, pending, q, picker=None):
    t, f = d["t"], d["f"]
    t0 = t.min()
    times = t - t0
    tm = np.ones(len(t), bool)
    fm = frequencies(d["spw"], d["ch"], q.get("spw", "").strip())
    zoom = q.get("zoom", {})
    for axis, coords, mask in [("t", times, tm), ("f", f, fm)]:
        if axis in zoom:
            lo, hi = zoom[axis]
            mask &= (coords >= lo) & (coords <= hi)
    ti = np.flatnonzero(tm)
    fi = np.flatnonzero(fm)
    w = w[ti][:, fi]
    pending = pending[ti][:, fi]
    before = w
    if q.get("after"):
        w = np.where(pending, 0, w)
    v = d["v"][ti][:, fi]
    tsec = float(q.get("seconds", 4))
    nc = int(q.get("channels", 1))
    if not np.isfinite(tsec) or tsec <= 0 or nc <= 0:
        raise ValueError("Averaging bins must be positive")
    fig = Figure(figsize=(11.6, 7.5), dpi=110)
    canvas = FigureCanvasAgg(fig)
    grid = fig.add_gridspec(2, 2, left=0.09, right=0.98, bottom=0.075, top=0.95, hspace=0.39, wspace=0.22)
    panels = {}
    for row in range(2):
        for col in range(2):
            stack = grid[row, col].subgridspec(2, 1, hspace=0.15)
            amp = fig.add_subplot(stack[0])
            phase = fig.add_subplot(stack[1], sharex=amp)
            amp.tick_params(labelbottom=False)
            amp.xaxis.get_offset_text().set_visible(False)
            panels[row, col] = amp, phase

    def bins(groups, coords):
        _, inv = np.unique(groups, axis=0, return_inverse=True)
        inv = inv.ravel()
        return inv, np.bincount(inv, weights=coords) / np.bincount(inv)

    def points(pair, x, z, color, full, partial):
        for ax, y in zip(pair, (np.abs(z), np.angle(z, deg=True))):
            ax.plot(x, y, ".", ms=size, color=color, mew=0)
            for mask, marker, edge in [(full, "o", "#922A84"), (partial, "s", "#AE6300")]:
                if mask.any():
                    ax.plot(
                        x[mask],
                        y[mask],
                        ls="none",
                        marker=marker,
                        ms=size + 2.5,
                        mfc="none",
                        mec=edge,
                        mew=0.65,
                        alpha=0.32 if mask.sum() > 1000 else 0.9,
                        zorder=1.9,
                    )

    size = float(q.get("size", 3))
    tg, tx = bins(np.floor(times[ti] / tsec), times[ti])
    fg, fx = bins(np.column_stack((d["spw"][fi], d["ch"][fi] // nc)), f[fi])
    for j, h in enumerate(HANDS):
        if h not in q.get("hands", HANDS):
            continue
        z, wt = v[:, :, j], w[:, :, j]
        marked = pending[:, :, j] if not q.get("after") else np.zeros(wt.shape, bool)
        total = z * wt
        for row, (inv, x, axis) in enumerate([(tg, tx, 1), (fg, fx, 0)]):

            def reduce(values):
                return np.bincount(inv, weights=values.sum(axis, dtype=float))

            den = reduce(wt)
            good = den > 0
            means = (reduce(total.real)[good] + 1j * reduce(total.imag)[good]) / den[good]
            hits = reduce(marked)[good]
            n = reduce(before[:, :, j] > 0)[good]
            if picker is not None:
                groups = np.flatnonzero(good)

                def identify(k, groups=groups, inv=inv, row=row):
                    inside = inv == groups[k]
                    return (ti[inside], fi) if row == 0 else (ti, fi[inside])

                picker.add(row, 0, h, x[good], means, identify)
            points(panels[row, 0], x[good], means, COLORS[h], hits == n, (hits > 0) & (hits < n))
        i, k = np.nonzero(wt > 0)
        hits = marked[i, k]
        for row, x in enumerate([times[ti][i], f[fi][k]]):
            if picker is not None:

                def identify(n, i=i, k=k):
                    return [ti[i[n]]], [fi[k[n]]]

                picker.add(row, 1, h, x, z[i, k], identify)
            points(panels[row, 1], x, z[i, k], COLORS[h], hits, np.zeros(len(i), bool))
    geometries = []
    for row, (key, coord, label) in enumerate(
        [("t", times, "Seconds after " + utc(t0)[11:23] + " UTC"), ("f", f[fm], "Frequency (GHz)")]
    ):
        for col in range(2):
            amp, phase = panels[row, col]
            amp.set_title(
                ("Time" if row == 0 else "Frequency")
                + "  ·  "
                + ("Weighted averages" if col == 0 else "Native samples"),
                fontsize=11,
            )
            phase.set_xlabel(label)
            if key == "f":
                phase.xaxis.set_major_formatter(ScalarFormatter(useOffset=False))
            phase.set_ylabel("Phase (°)")
            amp.set_ylabel("Amplitude")
            phase.set_ylim(-180, 180)
            phase.set_yticks([-180, 0, 180])
            if key in zoom:
                phase.set_xlim(zoom[key])
            elif len(coord):
                pad = max(np.ptp(coord) * 0.025, 0.000001)
                phase.set_xlim(coord.min() - pad, coord.max() + pad)
            if "y" in zoom:
                amp.set_ylim(zoom["y"])
            elif q.get("limits"):
                amp.set_ylim(q["limits"][len(geometries)])
            else:
                amp.set_ylim(bottom=0)
            for ax in (amp, phase):
                ax.grid(alpha=0.18)
                if not any(len(line.get_xdata()) for line in ax.lines):
                    ax.text(
                        0.5,
                        0.5,
                        "No visible valid samples",
                        ha="center",
                        transform=ax.transAxes,
                        fontsize=8,
                    )
                x, y, width, height = ax.get_position().bounds
                geometries.append(
                    dict(
                        axis=key,
                        amplitude=ax is amp,
                        box=[x, 1 - y - height, width, height],
                        x=ax.get_xlim(),
                        y=ax.get_ylim(),
                    )
                )
    if picker is not None:
        picker.geometry = geometries
    buf = io.BytesIO()
    canvas.print_png(buf)
    return dict(
        image=base64.b64encode(buf.getvalue()).decode(), axes=geometries, valid=int((w > 0).sum())
    )


def diagnostic(path, pair, nspw, q):
    """Read-only supplemental evidence from the report's channel-spectrum cache."""
    with np.load(path) as src:
        x = src["frequency"]
        a = src[pair.replace("&", "-")][int(q.get("quantity") == "Phase")]
    if len(x) % nspw:
        raise ValueError("Diagnostic channel grid does not match SPWs")
    fig = Figure(figsize=(11, 2.8), dpi=115)
    ax = fig.subplots()
    for j, p in enumerate(HANDS):
        if p not in q.get("hands", HANDS):
            continue
        ax.plot(x, a[:, j], ".", ms=q.get("size", 3), color=COLORS[p])
    ax.set(
        xlabel="Frequency (GHz)",
        ylabel="Phase (°)" if q.get("quantity") == "Phase" else "Amplitude (Jy)",
        title="Report diagnostic · scan average · original spectrum",
    )
    fig.tight_layout()
    buf = io.BytesIO()
    FigureCanvasAgg(fig).print_png(buf)
    return dict(image=base64.b64encode(buf.getvalue()).decode())
