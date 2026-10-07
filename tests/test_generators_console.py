"""
Unit tests for generators/console.py: a tbot JSON log printed as tbot
showed it on the console.

The events are written as tbot.log writes them (json.dump(indent=2), one
after the other); the expected lines follow tbot.log.EventIO and
tbot.log_event.
"""

import json
import os

from conftest import load_module

console = load_module(
    "tbottest_generators_console",
    os.path.join(os.path.dirname(__file__), "..", "generators", "console.py"),
)


def log(*events):
    return "".join(json.dumps(ev, indent=2) + "\n" for ev in events)


def ev(ty, **data):
    return {"type": ty, "time": 0.0, "data": data}


RUN = log(
    ev(["msg", "INFO"], text="TBOT.FLAGS ['do_power']"),
    ev(["tc", "begin"], name="outer"),
    ev(["board", "on", "amc"]),
    ev(["board", "uboot", "amc"], output="U-Boot 2026.07\r\nDRAM:  64 MiB\n"),
    ev(["tc", "begin"], name="inner"),
    ev(["cmd", "amc-uboot"], cmd="version", stdout="U-Boot 2026.07\n"),
    ev(["tc", "end"], name="inner", duration=0.5, success=True, skipped=False),
    ev(["msg", "CHANNEL"], text="only with -v"),
    ev(["board", "off", "amc"]),
    ev(["tc", "end"], name="outer", duration=1.25, success=False, skipped=False),
    ev(["exception"], name="RuntimeError", trace="Traceback\n  boom\n"),
    ev(["msg", "INFO"], text="─" * 4),
    ev(["tbot", "end"], success=False, duration=1.5),
)

EXPECTED = [
    "tbot starting ...",
    "├─TBOT.FLAGS ['do_power']",
    "├─Calling outer ...",
    "│   ├─POWERON (amc)",
    "│   ├─UBOOT (amc)",
    "│   │    <> U-Boot 2026.07",
    "│   │    <> DRAM:  64 MiB",
    "│   ├─Calling inner ...",
    "│   │   ├─[amc-uboot] version",
    "│   │   │    ## U-Boot 2026.07",
    "│   │   └─Done. (0.500s)",
    "│   ├─POWEROFF (amc)",
    "│   └─Fail. (1.250s)",
    "├─Exception:",
    "│   Traceback",
    "│     boom",
    "├─────",
    "└─FAILURE (1.500s)",
]


def test_run_as_on_the_console():
    assert console.render(RUN) == EXPECTED


def test_verbosity_like_tbot():
    more = console.render(RUN, console.STDOUT + 1)
    assert "│   ├─only with -v" in more
    quiet = console.render(RUN, console.QUIET)
    assert "│   │   ├─[amc-uboot] version" not in quiet
    assert "│   │    <> U-Boot 2026.07" not in quiet
    assert "├─Calling outer ..." in quiet


def test_skipped_testcase():
    lines = console.render(
        log(
            ev(["tc", "begin"], name="t"),
            ev(["tc", "end"], name="t", duration=0.0, success=True, skipped=True,
               skip_reason="no board"),
        )
    )
    assert lines[-1] == "│   └─Skipped: no board"


def test_color_codes_only_with_color():
    colored = console.render(log(ev(["tc", "begin"], name="t")), color=True)
    assert "\x1b[" in colored[1]
    plain = console.render(log(ev(["msg", "INFO"], text="\x1b[32mgreen\x1b[0m")))
    assert plain[1] == "├─green"


def test_events_one_after_the_other():
    assert [e["type"] for e in console.events(log(ev(["a"]), ev(["b"])))] == [["a"], ["b"]]


def test_start_event_when_tbot_logs_it():
    begin = ev(["tbot", "begin"], date="2026-10-06 12:19:30", argv=["@args", "tc"])
    lines = console.render(log(begin, ev(["msg", "INFO"], text="m")))
    assert lines == ["tbot starting ...", "├─m"]
    more = console.render(log(begin), console.STDOUT + 1)
    assert more == ["tbot starting ...", "  date: 2026-10-06 12:19:30", "  argv: ['@args', 'tc']"]
