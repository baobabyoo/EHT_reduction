"""Local visibility flag review. See README.md for usage."""
import argparse
import hashlib
import json
from pathlib import Path
import secrets
import threading
import webbrowser
from functools import lru_cache
import numpy as np
from flask import Flask, request, jsonify, Response, abort
from werkzeug.serving import make_server
from visibility import Visibility, HANDS
from selections import (
    Journal,
    command,
    command_lines,
    pdf_commands,
    axes,
    baseline_matches,
    frequencies,
    utc,
    intervals,
)
from charts import draw, diagnostic
from outliers import PickView

NATIVE = "channelized_working_copy.ms"
BLANK = dict(vis="", mode="manual", field="", antenna="", scan="", timerange="", spw="", correlation="")


class Review:
    def __init__(self, args):
        path = Path(args.vis).resolve()
        log = args.scan_log
        self.primary = Visibility(path, log, args.scan_gap, args.casa_python, args.field)
        self.queue = pdf_commands(args.pdf) if args.pdf else []
        ascii_path = getattr(args, "commands", None)
        if ascii_path:
            self.queue = command_lines(Path(ascii_path).read_text(encoding="utf-8-sig"))
            if not self.queue:
                raise ValueError("No flagdata calls in the command file")
        self.examine = bool(self.queue and getattr(args,"examine",False))
        self.positions = []
        if not self.queue or self.examine:
            for scan in np.unique(self.primary.scans):
                self.positions.extend((int(scan), pair) for pair in self.primary.baselines(scan))
            if not self.positions:
                raise ValueError("No cross-correlation baselines in this visibility file")
        self.targets = {self.primary.target: self.primary, Path(self.primary.target).name: self.primary}
        if any(e["k"].get("field") not in ("", None, self.primary.field) for e in self.queue):
            raise ValueError("Report field differs from visibility data")
        clock = self.primary
        if args.pdf and path.is_dir() and path.with_suffix(".uvf").is_file():
            sibling = path.with_suffix(".uvf")
            clock = Visibility(sibling, log, args.scan_gap)
        spans = {}
        if self.queue and not clock.is_ms:
            for scan in np.unique(clock.scans):
                times = clock.time[clock.scans == scan]
                spans[int(scan)] = (times.min() - 0.00005, times.max() + 0.00005)
        for item in self.queue:
            k = item["k"]
            if clock.local_scans and (k.get("scan") or (args.pdf and not k.get("timerange"))):
                raise ValueError("Local time-gap labels cannot identify original scans. Supply --scan-log for this review.")
            if clock.local_scans and args.pdf:
                ranges = intervals(k["timerange"])
                matches = [scan for scan, (lo, hi) in spans.items()
                           if any(start <= hi and end >= lo for start, end in ranges)]
                if len(matches) != 1:
                    raise ValueError("Cannot identify a unique scan from report UTC. Supply --scan-log.")
                item["scan"] = matches[0]
            if args.pdf and not clock.is_ms and k.get("scan") and int(k["scan"]) != item["scan"]:
                raise ValueError("PDF scan label and flag command disagree")
            if ascii_path:
                if k["vis"] not in self.targets and Path(k["vis"]).resolve() != Path(self.primary.target):
                    raise ValueError(f"Line {item['line']}: vis does not match {self.primary.target}")
                bounds = self.primary.bounds if self.primary.is_ms else spans
                candidates = sorted(bounds)
                if k.get("scan"):
                    candidates = [s for s in candidates if s == int(k["scan"])]
                if k.get("timerange"):
                    ranges = intervals(k["timerange"])
                    candidates = [
                        s
                        for s in candidates
                        if any(bounds[s][1] >= lo and bounds[s][0] <= hi for lo, hi in ranges)
                    ]
                item["scan"] = next(
                    (
                        s
                        for s in candidates
                        if any(baseline_matches(b, k["antenna"]) for b in self.primary.baselines(s))
                    ),
                    None,
                )
                if item["scan"] is None:
                    raise ValueError(f"Line {item['line']}: no matching scan and baseline")
            item["diagnostic"] = k["vis"] == NATIVE
            item["source_scan"] = item["scan"]
            k["vis"] = self.primary.target
            if k.get("scan") and item["scan"] in spans:
                lo, hi = spans[item["scan"]]
                if np.any((clock.time >= lo) & (clock.time <= hi) & (clock.scans != item["scan"])):
                    raise ValueError("Scan overlaps another scan in UTC; review on the target MS")
                ranges = intervals(k["timerange"]) if k.get("timerange") else [(lo, hi)]
                pieces = [
                    utc(max(lo, start)) + "~" + utc(min(hi, end))
                    for start, end in ranges
                    if start <= hi and end >= lo
                ]
                if not pieces:
                    raise ValueError("Scan and timerange do not overlap")
                k["timerange"] = ",".join(pieces)
                k.pop("scan")
            if args.pdf and self.primary.is_ms and k.get("timerange"):
                ranges = intervals(k["timerange"])
                ids = [
                    i
                    for i, (a, b) in self.primary.bounds.items()
                    if any(b >= lo and a <= hi for lo, hi in ranges)
                ]
                if len(ids) != 1:
                    raise ValueError(
                        f"Ambiguous MS scan for {k['timerange']}. Open the matching UVFITS export."
                    )
                item["scan"] = ids[0]
        if self.primary.is_ms and not spans and any(e["source_scan"] != e["scan"] for e in self.queue):
            if any(e["k"].get("scan") and not e["k"].get("timerange") for e in self.queue):
                raise ValueError(
                    "The report and MS use different scan numbering. Open the original UVFITS with its observing log, or place that export beside the same-stem MS."
                )
        key = dict(
            data=str(path),
            size=path.stat().st_size,
            field=self.primary.field,
            pdf=hashlib.sha256(Path(args.pdf).read_bytes()).hexdigest() if args.pdf else "",
            native=str(Path(args.native_ms).resolve()) if args.native_ms else "",
            scanlog=str(clock.scan_log or log or ""),
            gap=args.scan_gap,
        )
        if clock.scan_source.startswith("UVFITS "):
            key["embedded_scans"] = hashlib.sha256(clock.scans.tobytes()).hexdigest()
        if ascii_path:
            key["commands"] = hashlib.sha256(Path(ascii_path).read_bytes()).hexdigest()
        output = Path(args.output)
        if not output.is_absolute() and Path.cwd().resolve() == Path(__file__).resolve().parent:
            output = path.parent / output
        if ascii_path and Path(ascii_path).resolve() == output.resolve():
            raise ValueError("Choose a separate output file for this review")
        protected = [path, *(Path(p).resolve() for p in (args.pdf, ascii_path, log) if p)]
        output = output.resolve()
        if output in protected or any(p.is_dir() and p in output.parents for p in protected):
            raise ValueError("Choose a separate output file outside the science input")
        self.proposals = []
        if self.examine:
            key["examine"] = True
            self.proposals, self.queue = self.queue, []
            self.scan_bounds = self.primary.bounds if self.primary.is_ms else spans
        self.log = Journal(output, key, overwrite=getattr(args, "overwrite", False))
        self.pick_view = None
        self.references = (
            Path(args.pdf).resolve().parent
            / (path.stem.split("_calibrated")[0] + "_checkpoints")
            / "channels"
            if args.pdf
            else None
        )
        self.source = str(path)
        self.report = str(args.pdf or ascii_path or "")

    @property
    def steps(self):
        return self.log.data["steps"]

    def approved_items(self):
        for step_index, step in enumerate(self.steps):
            for offset, item in enumerate(step["items"]):
                yield f"{step_index}.{offset}", item

    def sidebar(self):
        rows = []
        for uid, item in self.approved_items():
            k = item["k"]
            antenna = k["antenna"].split("&", 1)[0].split(",", 1)[0]
            rows.append(dict(uid=uid, text=command(k), antenna=antenna,
                             number=self.primary.antenna_ids.get(antenna)))
        # A stable sort preserves approval order within each antenna.
        return sorted(rows, key=lambda r: (r["number"] is None, r["number"], r["antenna"]))

    @lru_cache(maxsize=1)
    def read(self, ds, scan, pair):
        return ds.read(scan, pair)

    def state(self, scan=None, pair=None):
        index = len(self.steps)
        item = self.queue[index] if index < len(self.queue) else None
        ds = self.targets.get(item["k"]["vis"], self.primary) if item else self.primary
        scans = (
            sorted(map(int, np.unique(ds.scans)))
            if self.queue
            else sorted({s for s, _ in self.positions})
        )
        if item:
            scan = item["scan"]
        elif scan is None and self.steps:
            scan = self.steps[-1].get("nextScan")
        scan = int(scans[0] if scan is None else scan)
        if scan not in scans:
            raise ValueError(f"Scan {scan} unavailable. Supply matching scan IDs / --scan-log.")
        pairs = ds.baselines(scan)
        if item:
            pairs = [p for p in pairs if baseline_matches(p, item["k"]["antenna"])]
        if not pairs:
            raise ValueError("No matching baseline for this scan and command")
        if not item and pair is None and self.steps and scan == self.steps[-1].get("nextScan"):
            pair = self.steps[-1].get("nextPair")
        if pair not in pairs:
            pair = pairs[0]
            if item and len(pairs) > 1 and not ds.is_ms:
                # Choose the partner with the most valid matching samples.
                def support(b):
                    d = self.read(ds, scan, b)
                    sel = axes(item["k"], d, scan, b, ds.field)
                    if sel is None:
                        return 0
                    t, f, h = sel
                    if not f.any() and item["diagnostic"]:
                        f = np.ones(len(f), bool)
                    return np.count_nonzero(d["w"][np.ix_(t, f, h)] > 0)

                pair = max(pairs, key=support)
        position = self.positions.index((scan, pair)) if self.positions else None
        target = item["k"]["vis"] if item else ds.target
        suggestions = []
        if self.examine:
            approved = [entry["k"] for _, entry in self.approved_items()]
            lo, hi = self.scan_bounds[scan]
            for candidate in self.proposals:
                k = candidate["k"]
                if k in approved or not baseline_matches(pair,k["antenna"]):
                    continue
                if k.get("scan") and int(k["scan"]) != scan:
                    continue
                if k.get("timerange") and not any(b >= lo and a <= hi for a,b in intervals(k["timerange"])):
                    continue
                suggestions.append(candidate)
        return dict(
            index=index,
            previous=self.positions[position - 1] if position is not None and position > 0 else None,
            following=self.positions[position + 1]
            if position is not None and position + 1 < len(self.positions)
            else None,
            blank=not item and not suggestions,
            total=len(self.queue),
            done=bool(self.queue and index >= len(self.queue)),
            pdf=bool(self.queue),
            scan=scan,
            scans=scans,
            scan_source=ds.scan_source,
            pair=pair,
            pairs=pairs,
            context=target not in self.targets,
            command="\n".join(command(e["k"]) for e in suggestions) or command(item["k"] if item else dict(BLANK, vis=ds.target)),
            reason=item["reason"] if item else "\n".join(dict.fromkeys(e["reason"] for e in suggestions)),
            target=target,
            field=ds.field,
            source=self.source,
            report=self.report,
            out=str(self.log.out),
            approved_commands=self.sidebar(),
            approved=sum(bool(s["items"]) for s in self.steps),
            iterate=not self.queue and (not self.steps or self.steps[-1].get("iterate", True)),
            reference=bool(
                item
                and item["diagnostic"]
                and not ds.local_scans
                and self.references
                and (self.references / f"scan{item['source_scan']}.npz").is_file()
            ),
        )

    def context(self, q):
        index = len(self.steps)
        if q["index"] != index:
            raise ValueError("Review already advanced. Reload this window.")
        item = self.queue[index] if index < len(self.queue) else None
        if self.queue and not item:
            raise ValueError("Report review complete")
        target = item["k"]["vis"] if item else self.primary.target
        ds = self.targets.get(target, self.primary)
        scan = int(q["scan"])
        pair = q["pair"]
        if item and (scan != item["scan"] or not baseline_matches(pair, item["k"]["antenna"])):
            raise ValueError("Selection outside current report item")
        if pair not in ds.baselines(scan):
            raise ValueError("Unknown baseline in scan")
        return ds, target, self.read(ds, scan, pair)

    def items(self, q, ds, target, d):
        result = command_lines(q["text"], q.get("reason", ""))
        for item in result:
            k = item["k"]
            if k["vis"] not in self.targets:
                raise ValueError(f"Line {item['line']}: command target must match {target}")
            k["vis"] = target
            if not ds.is_ms and k.get("scan"):
                raise ValueError(f"Line {item['line']}: use the scan UTC interval for a UVFITS import")
            if k.get("field") not in (None, "", ds.field):
                raise ValueError(f"Line {item['line']}: different target field")
        if not result:
            raise ValueError("Add a command first")
        return result

    def plot(self, q):
        ds, target, d = self.context(q)
        w = d["w"].copy()
        unchecked = set(q.get("unchecked", ()))
        for uid, item in self.approved_items():
            if uid in unchecked:
                continue
            k = item["k"]
            if self.targets.get(k["vis"]) is not ds:
                continue
            sel = axes(k, d, int(q["scan"]), q["pair"], ds.field)
            if sel is not None:
                w[np.ix_(*sel)] = 0
        selected = np.zeros(w.shape, bool)
        missing = []
        error = ""
        try:
            pending = self.items(q, ds, target, d)
        except (ValueError, SyntaxError, TypeError) as exc:
            pending = []
            error = str(exc)
        for item in pending:
            k = item["k"]
            selection = axes(k, d, int(q["scan"]), q["pair"], ds.field)
            if selection is None:
                continue
            t, f, p = selection
            if not f.any():
                missing.append(k.get("spw", ""))
            selected[np.ix_(t, f, p)] = True
        selected &= w > 0
        picker = PickView() if q.get("pickable") else None
        result = draw(d, w, selected, q, picker)
        if picker:
            picker.context = (len(self.steps), int(q["scan"]), q["pair"])
            result["pickToken"] = picker.token
        self.pick_view = picker
        result.update(affected=int(selected.sum()), missing=missing, error=error, ready=bool(pending))
        return result

    def outliers(self, q, finish):
        ds, target, d = self.context(q)
        picker = self.pick_view
        if (
            not picker
            or picker.token != q["token"]
            or picker.context != (len(self.steps), int(q["scan"]), q["pair"])
        ):
            raise ValueError("This plot has changed. Reopen Pick outliers.")
        if finish:
            base = dict(
                vis=target,
                mode="manual",
                field=ds.field,
                antenna=q["pair"],
                scan=str(q["scan"]) if ds.is_ms else "",
            )
            return dict(commands=picker.commands(d, base, q["ids"]))
        return picker.nearest(q["panel"], q["x"], q["y"], q["width"], q["height"])

    def selection(self, q):
        ds, target, d = self.context(q)
        t = d["t"]
        zoom = q.get("zoom", {})
        lo, hi = zoom.get("t", [0, t.max() - t.min()])
        if not ((t - t.min() >= lo) & (t - t.min() <= hi)).any():
            raise ValueError("No integrations inside the selected time range")
        f = frequencies(d["spw"], d["ch"], q.get("spw", ""))
        if "f" in zoom:
            a, b = zoom["f"]
            f &= (d["f"] >= a) & (d["f"] <= b)
        if not f.any():
            raise ValueError("No channels inside selected frequency range")
        groups = []
        for s in np.unique(d["spw"][f]):
            chans = np.unique(d["ch"][f & (d["spw"] == s)])
            runs = np.split(chans, np.flatnonzero(np.diff(chans) > 1) + 1)
            text = ";".join(str(r[0]) if len(r) == 1 else f"{r[0]}~{r[-1]}" for r in runs)
            groups.append(str(s) if len(chans) == sum(d["spw"] == s) else f"{s}:{text}")
        # Round outwards; a formatted boundary must retain its edge integration.
        return dict(
            vis=target,
            mode="manual",
            field=ds.field,
            antenna=q["pair"],
            scan=str(q["scan"]) if ds.is_ms else "",
            timerange=utc(t.min() + max(0, lo) - 0.00005)
            + "~"
            + utc(min(t.max(), t.min() + hi) + 0.00005),
            spw=",".join(groups),
            correlation="RR,RL,LR,LL",
        )

    def decide(self, q):
        ds, target, d = self.context(q)
        items = self.items(q, ds, target, d) if q["approve"] else []
        next_scan, next_pair = int(q["scan"]), q["pair"]
        advance = not self.queue and q.get("iterate", False)
        if advance:
            position = self.positions.index((next_scan, next_pair))
            if position + 1 < len(self.positions):
                next_scan, next_pair = self.positions[position + 1]
            else:
                advance = False
        self.log.add(
            dict(
                scan=q["scan"],
                pair=q["pair"],
                items=items,
                nextScan=next_scan,
                nextPair=next_pair,
                iterate=advance,
            )
        )
        return self.state()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vis")
    parser.add_argument("other_table", nargs="?", help="Optional companion passband calibration table")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--pdf")
    source.add_argument("--commands", "--ascii", help="ASCII command file, one flagdata call per line")
    parser.add_argument("--native-ms", help=argparse.SUPPRESS)  # accept older launch commands
    parser.add_argument("--scan-log")
    parser.add_argument("--scan-gap", type=float, default=60)
    parser.add_argument("--field")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace the output flag file and reset its review journal",
    )
    parser.add_argument("--output", default="approved_flags.py")
    parser.add_argument("--casa-python", help="Path to the CASA Python interpreter")
    parser.add_argument("--examine", action="store_true", help="Browse all data with imported commands suggested at matching plots")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    fringe_mode = Path(args.vis).is_dir() and Path(args.vis).suffix.lower() == ".t"
    if not args.casa_python:
        fringe_python = Path.home() / "Applications/CASA-6.6.6-Intel.app/Contents/MacOS/python3"
        args.casa_python = str(fringe_python) if fringe_mode and fringe_python.exists() else "/Applications/CASA.app/Contents/MacOS/python3"
    from bandpass import KINDS, Bandpass
    passband = Path(args.vis).name in KINDS
    if args.other_table and (not passband or Path(args.other_table).name not in KINDS):
        parser.error("The second input must be a companion passband table")
    if passband:
        review = Bandpass(args)
    elif fringe_mode:
        from fringe import Fringe
        review = Fringe(args)
    else:
        review = Review(args)
    app = Flask(__name__, static_folder=None)
    token = secrets.token_urlsafe(24)

    @app.route("/" + token + "/")
    def home():
        return Response(Path(__file__).with_name("bandpass.html" if passband else "fringe.html" if fringe_mode else "review.html").read_text(), mimetype="text/html")

    @app.route("/" + token + "/calibration_queue.js")
    def calibration_script():
        return Response(Path(__file__).with_name("calibration_queue.js").read_text(), mimetype="text/javascript")

    @app.route("/" + token + "/<action>", methods=["POST"])
    def api(action):
        if not request.is_json:
            abort(415)
        try:
            q = request.get_json()
            if fringe_mode or passband:
                if action == "exit":
                    imp=review.imported
                    if imp.entries and not imp.examine:
                        remaining=imp.entries[len(review.log.data["steps"]):]
                        review.log.add_many([dict(keys=[],calls=[],skipped=True) for _ in remaining])
                    threading.Thread(target=server.shutdown, daemon=True).start()
                    return jsonify(out=str(review.log.out))
                imported = review.imported
                if action in ("approve", "skip"):
                    imported.check(review,q)
                if action == "skip":
                    review.log.add(dict(keys=[],calls=[],skipped=True))
                    return jsonify({})
                result = review.api(action, q)
                if action == "state":
                    result["review"] = imported.status(review)
                return jsonify(result)
            if action == "state":
                return jsonify(review.state(q.get("scan"), q.get("pair")))
            if action in ("pick-point", "finish-picks"):
                return jsonify(review.outliers(q, action == "finish-picks"))
            if action == "plot":
                return jsonify(review.plot(q))
            if action == "exit":
                if q["index"] != len(review.steps):
                    raise ValueError("Review position changed. Reload before exiting.")
                if review.queue:
                    rest = review.queue[len(review.steps) :]
                    review.log.add_many([dict(scan=e["scan"], items=[], skipped=True) for e in rest])
                elif q.get("iterate"):
                    position = review.positions.index((int(q["scan"]), q["pair"]))
                    remaining = review.positions[position:]
                    review.log.add_many(
                        [
                            dict(
                                scan=s,
                                pair=p,
                                items=[],
                                skipped=True,
                                nextScan=s,
                                nextPair=p,
                                iterate=False,
                            )
                            for s, p in remaining
                        ]
                    )
                threading.Thread(target=server.shutdown, daemon=True).start()
                return jsonify(out=str(review.log.out))
            if action == "reference":
                ds, target, d = review.context(q)
                if not review.queue or not review.references:
                    raise ValueError("No report diagnostic")
                return jsonify(
                    diagnostic(
                        review.references / f"scan{review.queue[q['index']]['source_scan']}.npz",
                        q["pair"],
                        len(set(d["spw"])),
                        q,
                    )
                )
            if action == "selection":
                return jsonify(review.selection(q))
            if action == "decide":
                return jsonify(review.decide(q))
            abort(404)
        except (ValueError, KeyError, SyntaxError, TypeError, IndexError) as e:
            return jsonify(error=str(e)), 400

    server = make_server("127.0.0.1", 0, app)
    url = f"http://127.0.0.1:{server.server_port}/{token}/"
    print("Open " + url, flush=True)
    if not args.no_browser:
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()
    server.serve_forever()


if __name__ == "__main__":
    main()
