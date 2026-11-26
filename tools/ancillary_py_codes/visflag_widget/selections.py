"""Literal CASA selections and review journal. Command text is never evaluated."""
import ast
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from visibility import HANDS

KEYS = {"vis", "mode", "field", "scan", "antenna", "timerange", "spw", "correlation"}


def command(k):
    return "flagdata(" + ", ".join(f"{name}={value!r}" for name, value in k.items()) + ")"


def numbers(spec):
    if not re.fullmatch(r"\d+(~\d+)?", spec):
        raise ValueError("Use integer IDs or inclusive a~b ranges")
    a, *b = map(int, spec.split("~"))
    if b and b[0] < a:
        raise ValueError("Reversed range")
    return a, b[0] if b else a


def matches(x, token):
    a, b = numbers(token)
    return (x >= a) & (x <= b)


def frequencies(spw, ch, spec):
    if not spec:
        return np.ones(len(ch), bool)
    mask = np.zeros(len(ch), bool)
    for term in spec.split(","):
        fields = term.split(":")
        if len(fields) > 2:
            raise ValueError("Expected SPW[:channel] selection")
        s = matches(spw, fields[0])
        if len(fields) == 2:
            chans = np.zeros(len(ch), bool)
            for group in fields[1].split(";"):
                chans |= matches(ch, group)
            s &= chans
        mask |= s
    return mask


def epoch(s):
    return (
        datetime.fromisoformat(s[:10].replace("/", "-") + "T" + s[11:])
        .replace(tzinfo=timezone.utc)
        .timestamp()
    )


def interval(s):
    a, b = map(epoch, s.split("~"))
    if a > b:
        raise ValueError("Reversed UTC interval")
    return a, b


def intervals(spec):
    return [interval(term) for term in spec.split(",")]


def utc(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y/%m/%d/%H:%M:%S.%f")


def baseline_matches(pair, expr):
    if not expr:
        return True
    a, b = pair.split("&")
    if "&" not in expr:
        return bool({a, b}.intersection(expr.split(",")))
    l, r = [set(x.split(",")) for x in expr.split("&")]
    return (a in l and b in r) or (b in l and a in r)


def parse(text):
    n = ast.parse(text.strip(), mode="eval").body
    if (
        not isinstance(n, ast.Call)
        or not isinstance(n.func, ast.Name)
        or n.func.id != "flagdata"
        or n.args
    ):
        raise ValueError("Enter a single flagdata call with literal keyword values")
    k = {v.arg: ast.literal_eval(v.value) for v in n.keywords}
    if set(k) - KEYS or len(k) != len(n.keywords) or not all(isinstance(v, str) for v in k.values()):
        raise ValueError("Unsupported or duplicate CASA parameter")
    if k.get("mode") != "manual" or not k.get("vis"):
        raise ValueError('Set vis and mode="manual"')
    if not k.get("antenna") or not (k.get("scan") or k.get("timerange")):
        raise ValueError("Specify an antenna/baseline and a scan or UTC interval")
    if not re.fullmatch(r"[\w.\-]+(?:,[\w.\-]+)*(?:&[\w.\-]+(?:,[\w.\-]+)*)?", k["antenna"]):
        raise ValueError("Use named stations or station&partner[,partner]")
    if k.get("scan") and not k["scan"].isdigit():
        raise ValueError("Select one numeric scan")
    if k.get("timerange"):
        intervals(k["timerange"])
    if k.get("correlation") and set(k["correlation"].split(",")) - set(HANDS):
        raise ValueError("Invalid correlation")
    frequencies(np.array([0]), np.array([0]), k.get("spw", ""))
    return k


def axes(k, d, scan, pair, field):
    if k.get("field") not in (None, "", field) or not baseline_matches(pair, k["antenna"]):
        return
    if k.get("scan") and int(k["scan"]) != scan:
        return
    t = np.ones(len(d["t"]), bool)
    if k.get("timerange"):
        t[:] = False
        for lo, hi in intervals(k["timerange"]):
            t |= (d["t"] >= lo) & (d["t"] <= hi)
    f = frequencies(d["spw"], d["ch"], k.get("spw", ""))
    p = np.array([not k.get("correlation") or h in k["correlation"].split(",") for h in HANDS])
    return t, f, p


def command_lines(text, reason=""):
    """Read one literal call per noncomment line, preserving file order."""
    commands = []
    comments = []
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            comments.append(line[1:].strip())
            continue
        try:
            kwargs = parse(line)
        except (SyntaxError, ValueError, TypeError) as exc:
            raise ValueError(f"Line {number}: {exc}") from exc
        commands.append(dict(k=kwargs, reason="\n".join(comments) or reason, line=number))
        comments.clear()
    return commands


def report_pages(path):
    try:
        from pdf_text import pages

        texts = pages(path)
    except ImportError:
        import subprocess

        python = (
            Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
        )
        if not python.exists():
            raise ValueError("Install pypdf using the instructions in README.md")
        texts = json.loads(
            subprocess.check_output(
                [str(python), str(Path(__file__).with_name("pdf_text.py")), str(path)]
            )
        )
    return texts


def pdf_commands(path):
    queue = []
    for s in report_pages(path):
        for m in re.finditer(r"^flagdata\([^)]*\)", s, re.M):
            k = parse(m.group())
            line = s[: m.start()].rstrip().splitlines()[-1]
            info = re.match(r"(?:\d+\s+)?Scan (\d+)\s+(?:/\s*)?(.*)", line)
            queue.append(
                dict(
                    k=k,
                    scan=int(info[1]) if info else int(k.get("scan") or 0),
                    reason=info[2] if info else "",
                )
            )
    if not queue:
        raise ValueError("No standalone CASA flagdata calls in PDF")
    return queue


def atomic(path, data):
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)


class Journal:
    def __init__(self, out, identity, overwrite=False):
        import fcntl

        self.out = Path(out).resolve()
        self.lock = self.out.with_suffix(self.out.suffix + ".lock").open("a")
        fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.path = self.out.with_suffix(self.out.suffix + ".review.json")
        self.data = {"identity": identity, "steps": []}
        if overwrite:
            self.data["reset_pending"] = True
            atomic(self.path, json.dumps(self.data).encode())
        if self.path.exists():
            self.data = json.loads(self.path.read_text())
            if self.data["identity"] != identity:
                raise ValueError("Choose a different output file for this input or report")
        elif self.out.exists():
            raise ValueError("Choose a new output path; existing file has no review journal")
        if self.data.pop("reset_pending", False):
            atomic(self.out, b"")
        self.sync()

    def contents(self, steps):
        lines = []
        for step in steps:
            for item in step["items"]:
                reason = item["reason"].strip() or "Approved during visibility review"
                lines.extend("# " + s for s in reason.splitlines())
                lines.extend([command(item["k"]), ""])
        return ("\n".join(lines) + ("\n" if lines else "")).encode("ascii", "backslashreplace")

    def sync(self):
        steps = self.data["steps"]
        if self.out.exists() and self.out.read_bytes() not in (
            self.contents(steps),
            self.contents(steps[:-1]),
        ):
            raise ValueError(
                "The approved file was externally edited; preserve it and choose a new output"
            )
        atomic(self.path, json.dumps(self.data, indent=2).encode())
        atomic(self.out, self.contents(steps))

    def add(self, step):
        self.add_many([step])

    def add_many(self, steps):
        if self.out.read_bytes() != self.contents(self.data["steps"]):
            raise ValueError("Output changed outside the widget")
        self.data["steps"].extend(steps)
        self.sync()
