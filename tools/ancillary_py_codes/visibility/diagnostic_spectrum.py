"""Read plotted markers from a CASA/rPICARD Cairo PostScript frequency diagnostic.

The review JSON records two labeled tick positions per axis (page coordinates
and physical values). Confirm these against each selected diagnostic page.
Marker coordinates are quantized plot values; they do not carry sample weights.
"""
import re
from pathlib import Path

import numpy as np


def read_channel_spectrum(root, review, centers, pols):
    config = review["channel_diagnostic"]
    source = Path(root) / config["file"]
    if source.name != f"{review['source']}_scan{review['scan']}_plots_vs_freq.ps":
        raise ValueError("Diagnostic source or scan differs from the review")
    selected = []
    with source.open("rb") as stream:
        active = False
        for line in stream:
            if line.startswith(b"%%Page:"):
                if active:
                    break
                active = int(line.split()[1]) == config["page"]
            if active:
                selected.append(line)
    page = b"".join(selected).decode("latin1")
    return decode_page(page, review, centers, pols)


def decode_page(page, review, centers, pols):
    config = review["channel_diagnostic"]
    name = "".join(review["baseline"])
    halves = page.split(f"({name})Tj")
    if len(halves) != 2 or "(Amp [Jy])Tj" not in halves[0] or "( [deg])Tj" not in halves[1]:
        raise ValueError("The page must contain the requested baseline and labeled amplitude and phase panels")

    # Map each source color to its actual legend label.
    blocks = re.split(r"(?m)^([.\d]+ [.\d]+ [.\d]+) rg$", halves[1])
    colors = {}
    for rgb, commands in zip(blocks[1::2], blocks[2::2]):
        label = re.search(r"\((RR|LL|LR|RL)\)Tj", commands)
        if label:
            colors[rgb] = label[1]
    if not colors or not set(colors.values()).issubset(pols) or len(set(colors.values())) != len(colors):
        raise ValueError("Ambiguous polarization legend")

    def calibrate(coordinate, axis):
        (x0, y0), (x1, y1) = config[axis]
        return y0 + (coordinate - x0) * (y1 - y0) / (x1 - x0)

    # Each dot is two cubic arcs. Their endpoints are the left and right edges.
    num = r"[-.\d]+"
    dot = re.compile(rf"({num})\s+({num})\s+m\s+{num}\s+{num}\s+{num}\s+{num}\s+({num})\s+{num}\s+c\s+(?:{num}\s+){{6}}c\s+f\b")
    channels = int(config["channels_per_if"])
    spacing = config["spacing_mhz"] / 1000
    offsets = (np.arange(channels) - (channels-1)/2) * spacing
    frequencies = (centers[:, None] + offsets).ravel()
    panels = []
    for half, axis in zip(halves, ["amplitude_jy", "phase_deg"]):
        values = np.full((frequencies.size, len(pols)), np.nan)
        sections = re.split(r"(?m)^([.\d]+ [.\d]+ [.\d]+) rg$", half)
        for color, section in zip(sections[1::2], sections[2::2]):
            dots = np.array(dot.findall(section), dtype=float)
            if not dots.size:
                continue
            x = calibrate((dots[:, 0] + dots[:, 2])/2, "frequency_ghz")
            spw = abs(x[:, None] - centers).argmin(axis=1)
            channel = np.rint((x - centers[spw])/spacing + (channels-1)/2).astype(int)
            if np.any((channel < 0) | (channel >= channels)):
                raise ValueError("Point falls outside the declared channel grid")
            idx = spw*channels + channel
            p = pols.index(colors[color])
            if np.max(abs(frequencies[idx] - x)) > .2*spacing:
                raise ValueError("Marker coordinates and channel frequencies disagree")
            if len(set(idx)) != len(idx) or np.isfinite(values[idx,p]).any():
                raise ValueError("Multiple plotted values at one channel; verify time averaging")
            values[idx,p] = calibrate(dots[:,1], axis)
        if np.isfinite(values).sum() != len(re.findall(r"\bc\s+f\b", half)):
            raise ValueError("Some plotted markers were not recovered")
        panels.append(values)
    if not np.array_equal(np.isfinite(panels[0]),np.isfinite(panels[1])) or not np.isfinite(panels[0]).any():
        raise ValueError("Inconsistent amplitude and phase marker sets")
    return frequencies, panels[0], panels[1]
