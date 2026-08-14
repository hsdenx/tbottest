"""
Unit tests for tbottest/tc/process.py's ps/top output parsers
(ps_parse_ps, ps_parse_top). Pure log-string parsing, no hardware
needed.
"""

import os

from conftest import install_fake_initconfig, install_real_submodule, load_module

install_fake_initconfig()
install_real_submodule(
    "tbottest.common.utils",
    os.path.join(os.path.dirname(__file__), "..", "tbottest", "common", "utils.py"),
)

process = load_module(
    "tbottest_tc_process",
    os.path.join(os.path.dirname(__file__), "..", "tbottest", "tc", "process.py"),
)


class TestPsParsePs:
    def test_empty_log_returns_empty_list(self):
        assert process.ps_parse_ps("") == []

    def test_parses_lines_after_header(self):
        log = "\n".join(
            [
                "  PID   TID %CPU  NI PRI COMMAND",
                "  172   172  0.0   0  20 rngd",
                "  200   200  1.5   0  20 sshd",
            ]
        )
        result = process.ps_parse_ps(log)
        assert result == [
            {"PID": "172", "TID": "172", "CPU": "0.0", "NI": "0", "PRI": "20", "CMD": "rngd"},
            {"PID": "200", "TID": "200", "CPU": "1.5", "NI": "0", "PRI": "20", "CMD": "sshd"},
        ]

    def test_unparseable_line_is_skipped_not_fatal(self):
        log = "\n".join(
            [
                "  PID   TID %CPU  NI PRI COMMAND",
                "too few fields",  # fewer than 6 whitespace-separated tokens
                "  172   172  0.0   0  20 rngd",
            ]
        )
        result = process.ps_parse_ps(log)
        assert len(result) == 1
        assert result[0]["CMD"] == "rngd"


TOP_LOG_TWO_LOOPS = "\n".join(
    [
        "%Cpu(s): 74.4 us, 20.5 sy,  0.0 ni,  0.0 id,  0.0 wa,  0.0 hi,  5.1 si,  0.0 st",
        "MiB Mem :    491.0 total,    164.2 free,    143.9 used,    182.9 buff/cache",
        "MiB Swap:      0.0 total,      0.0 free,      0.0 used.    321.8 avail Mem",
        "  267 weston    20   0  243672  85304  13792 R  93.8  17.0  32:32.89 /usr/bin/weston --modules=systemd-notify.so",
        "%Cpu(s): 92.9 us,  6.2 sy,  0.0 ni,  0.9 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st",
        " 2119 root      20   0    4128   1944   1496 R   5.4   0.4   0:00.26 top -b -n 3 -d 1 -c -H",
    ]
)


class TestPsParseTop:
    def test_empty_log_returns_empty_list(self):
        assert process.ps_parse_top("", busybox=False) == []

    def test_both_loops_present(self):
        """
        Regression test: the last loop's data used to be silently
        dropped -- it was only ever flushed into the result list when
        the *next* "%Cpu(s):" marker line appeared, so whatever came
        after the final marker in the log was lost.
        """
        result = process.ps_parse_top(TOP_LOG_TWO_LOOPS, busybox=False)
        assert len(result) == 2

    def test_first_loop_values(self):
        result = process.ps_parse_top(TOP_LOG_TWO_LOOPS, busybox=False)
        first = result[0]
        assert first["loop"] == 1
        assert first["cpu_system"]["USER"] == "74.4"
        assert len(first["values"]) == 1
        assert first["values"][0]["CMD"] == "/usr/bin/weston"

    def test_last_loop_values(self):
        result = process.ps_parse_top(TOP_LOG_TWO_LOOPS, busybox=False)
        last = result[-1]
        assert last["loop"] == 2
        assert last["cpu_system"]["USER"] == "92.9"
        assert len(last["values"]) == 1
        assert last["values"][0]["CMD"] == "top"

    def test_mib_mem_and_swap_lines_ignored(self):
        result = process.ps_parse_top(TOP_LOG_TWO_LOOPS, busybox=False)
        # only the process line counts as a "value" per loop, not the
        # MiB Mem/Swap info lines
        assert all(len(loop["values"]) == 1 for loop in result)

    def test_busybox_format(self):
        log = "\n".join(
            [
                "CPU:   2% usr   2% sys   0% nic  95% idle   0% io   0% irq   0% sirq",
                "  PID  PPID USER     STAT   VSZ %VSZ %CPU COMMAND",
                "  123     1 root     S     1234   1%   0% init",
            ]
        )
        result = process.ps_parse_top(log, busybox=True)
        assert len(result) == 1
        assert result[0]["cpu_system"]["USER"] == "2"
        assert result[0]["values"][0]["CMD"] == "init"
