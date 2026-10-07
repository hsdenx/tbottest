#!/usr/bin/env python3
"""
Print a tbot JSON log (--json-log-stream) the way tbot showed the run on
the console: the tree of testcases, the commands with their output, the
boot logs of U-Boot and Linux, messages and exceptions.

    generators/console.py [-v | -q] [--color | --no-color] <logfile>

tbot writes an event to the log when it is done with it. A log without
the event ["tbot", "begin"] (tbot before it logged its start) gets the line
"tbot starting ..." printed first here; with the event, -v also shows the
start time and the arguments it records. The nesting
comes from the testcase begin and end events, as on the console. Output is
filtered by verbosity as tbot does it, by default up to the output of
commands; -v adds a level, -q removes one, as tbot's own -v and -q.
"""
import argparse
import json
import os
import re
import sys
import typing

# tbot.log.Verbosity
QUIET, INFO, COMMAND, STDOUT, CHANNEL = range(5)
VERBOSITY_NAMES = {"QUIET": QUIET, "INFO": INFO, "COMMAND": COMMAND, "STDOUT": STDOUT, "CHANNEL": CHANNEL}

ANSI = re.compile(r"\x1b\[[0-9;]*m")
LINE_SPLIT = re.compile(r"\r\n|\n|\r")


def events(text: str) -> typing.Iterator[dict]:
    """
    The log events of a tbot JSON log: JSON objects one after the other,
    as tbot.log writes them with json.dump(indent=2).
    """
    decoder = json.JSONDecoder()
    i = 0
    while True:
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            return
        ev, i = decoder.raw_decode(text, i)
        yield ev


class Console:
    """Renders log events to lines as tbot.log prints them."""

    def __init__(self, verbosity: int = STDOUT, color: bool = False) -> None:
        self.verbosity = verbosity
        self.color = color
        self.nesting = 0
        self.lines: typing.List[str] = []

    def c(self, text: str, *codes: int) -> str:
        if not self.color or not codes:
            return text
        return "".join(f"\x1b[{n}m" for n in codes) + text + "\x1b[0m"

    def _prefix(self, after: str, prefix: str = "") -> str:
        return self.c("│   " * self.nesting + after, 2) + prefix

    def head(self, text: str, verbosity: int, first: str = "├─") -> None:
        """first line of an event, the rest of a multi-line text below it"""
        parts = text.split("\n", 1)
        if verbosity <= self.verbosity:
            self.lines.append(self._prefix(first) + parts[0])
        if len(parts) > 1:
            self.body(parts[1], verbosity)

    def body(self, text: str, verbosity: int, prefix: str = "") -> None:
        """content lines of an event, below its first line"""
        if verbosity > self.verbosity or not text:
            return
        lines = LINE_SPLIT.split(text)
        if lines and lines[-1] == "":
            lines.pop()
        for line in lines:
            self.lines.append(self._prefix("│ ", prefix) + line)

    def event(self, ev: dict) -> None:
        ty = ev.get("type", []) or [""]
        handler = getattr(self, "_ev_" + ty[0], None)
        if handler is None or not handler(ty, ev.get("data", {})):
            self.head(f"{ty} {ev.get('data', {})}", INFO)

    def _ev_tc(self, ty: list, data: dict) -> bool:
        if ty[1:2] == ["begin"]:
            self.head("Calling " + self.c(data.get("name", ""), 36, 1) + " ...", QUIET)
            self.nesting += 1
            return True
        if ty[1:2] != ["end"]:
            return False
        duration = data.get("duration", 0.0)
        if data.get("skipped"):
            msg = self.c("Skipped", 33, 1) + f": {data.get('skip_reason', '')}"
        elif data.get("success", True):
            msg = self.c("Done", 32, 1) + f". ({duration:.3f}s)"
        else:
            msg = self.c("Fail", 31, 1) + f". ({duration:.3f}s)"
        self.head(msg, QUIET, "└─")
        self.nesting = max(self.nesting - 1, 0)
        return True

    def _ev_cmd(self, ty: list, data: dict) -> bool:
        mach = ty[1] if len(ty) > 1 else ""
        self.head("[" + self.c(mach, 33) + "] " + self.c(data.get("cmd", ""), 2), COMMAND)
        self.body(data.get("stdout", ""), STDOUT, "   ## ")
        return True

    def _ev_board(self, ty: list, data: dict) -> bool:
        name = ty[2] if len(ty) > 2 else ""
        if ty[1:2] in (["uboot"], ["linux"]):
            self.head(self.c(ty[1].upper(), 1) + f" ({name})", QUIET)
            self.body(data.get("output", ""), STDOUT, "   <> ")
            return True
        if ty[1:2] in (["on"], ["off"]):
            label = "POWERON" if ty[1] == "on" else "POWEROFF"
            self.head(self.c(label, 1) + f" ({name})", QUIET)
            return True
        return False

    def _ev_msg(self, ty: list, data: dict) -> bool:
        level = VERBOSITY_NAMES.get(ty[1] if len(ty) > 1 else "INFO", INFO)
        self.head(data.get("text", ""), level)
        return True

    def _ev_exception(self, ty: list, data: dict) -> bool:
        self.head(self.c("Exception", 31, 1) + ":", QUIET)
        self.body(data.get("trace", ""), QUIET, "  ")
        return True

    def _ev_tbot(self, ty: list, data: dict) -> bool:
        if ty[1:2] == ["begin"]:
            # at NESTING -1 tbot prints this without a tree prefix
            self.lines.append(self.c("tbot", 33, 1) + " starting ...")
            if self.verbosity >= CHANNEL:
                for key in ("date", "argv"):
                    if key in data:
                        self.lines.append(f"  {key}: {data[key]}")
            return True
        if ty[1:2] == ["end"]:
            ok = data.get("success", False)
            msg = self.c("SUCCESS", 32, 1) if ok else self.c("FAILURE", 31, 1)
            self.head(msg + f" ({data.get('duration', 0.0):.3f}s)", QUIET, "└─")
            return True
        return False


def render(text: str, verbosity: int = STDOUT, color: bool = False) -> typing.List[str]:
    """the console lines of a tbot JSON log"""
    con = Console(verbosity, color)
    evs = list(events(text))
    if not any(e.get("type", [])[:2] == ["tbot", "begin"] for e in evs):
        con.lines.append(con.c("tbot", 33, 1) + " starting ...")
    for ev in evs:
        con.event(ev)
    if not color:
        con.lines = [ANSI.sub("", line) for line in con.lines]
    return con.lines


def main(argv: typing.Optional[typing.List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    parser.add_argument("logfile", help="tbot JSON log, written with --json-log-stream")
    parser.add_argument("-v", action="count", default=0, help="more output, as tbot -v")
    parser.add_argument("-q", action="count", default=0, help="less output, as tbot -q")
    col = parser.add_mutually_exclusive_group()
    col.add_argument("--color", dest="color", action="store_true", default=None)
    col.add_argument("--no-color", dest="color", action="store_false")
    args = parser.parse_args(argv)

    color = sys.stdout.isatty() if args.color is None else args.color
    with open(args.logfile) as f:
        text = f.read()
    try:
        for line in render(text, STDOUT + args.v - args.q, color):
            print(line)
        sys.stdout.flush()
    except BrokenPipeError:
        # the reader, e.g. head or less, quit early; keep Python from
        # reporting the failed flush of stdout at exit
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
    return 0


if __name__ == "__main__":
    sys.exit(main())
