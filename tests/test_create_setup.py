"""
Tests for scripts/create_setup.sh.

The script is run for real in an empty directory, with an empty tbot
directory and a tbottest symlink to this checkout, so it clones
nothing. Its questions are answered on stdin. Every combination of
console and power control is checked: the generated tbot.ini must
hold the selected console and power control section with exactly the
values given, none of the other console and power control sections,
and it must resolve completely with the interpolation tbottest reads
it with.
"""

import configparser
import itertools
import os
import subprocess

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(REPO, "scripts", "create_setup.sh")
BOARD = "testboard"

LAB_ANSWERS = ["testlab", "192.168.1.200", "labuser", BOARD]

# name: (section prefix, answers in the order asked, expected section
# content, flag written to the args file or None)
CONSOLES = {
    "picocom": (
        "PICOCOM",
        ["57600", "/dev/ttyUSB7", "2", "False"],
        {"baudrate": "57600", "device": "/dev/ttyUSB7", "delay": "2", "noreset": "False"},
        "-fpicocom",
    ),
    "kermit": (
        "KERMIT",
        ["/home/pi/kermrc_test", "4"],
        {"cfgfile": "/home/pi/kermrc_test", "delay": "4"},
        None,
    ),
    "scriptcom": (
        "SCRIPTCOM",
        ["./myconnect.sh", "~~x"],
        {"scriptname": "./myconnect.sh", "exitstring": "~~x"},
        "-fscriptcom",
    ),
    "telnet": (
        "TELNET",
        ["consoleserver", "7001", "5"],
        {"host": "consoleserver", "port": "7001", "delay": "5"},
        "-ftelnet",
    ),
}

# name: (section prefix, answers in the order asked, expected section
# content)
POWERS = {
    "gpio": (
        "GPIOPMCTRL",
        ["23", "0"],
        {"gpiopmctl_pin": "23", "gpiopmctl_state": "0"},
    ),
    "sispmctrl": (
        "SISPMCTRL",
        ["01:02:03:04:05", "4"],
        {"device": "01:02:03:04:05", "port": "4"},
    ),
    "shell": (
        "POWERSHELLSCRIPT",
        ["/home/pi/power_test.sh"],
        # tbottest reads it with ast.literal_eval(), so it stays quoted
        {"script": '"/home/pi/power_test.sh"'},
    ),
    "tinkerforge": (
        "TF",
        ["Abc", "3"],
        {"uid": "Abc", "channel": "3"},
    ),
    "tbox": (
        "TBOX",
        ["P2_12V_EN"],
        {"powerpin": "P2_12V_EN"},
    ),
    "tm021": (
        "TM021",
        ["/dev/relais2", "115200", "7", "2", "3", "True"],
        {
            "device": "/dev/relais2",
            "baudrate": "115200",
            "timeout": "7",
            "address": "2",
            "port": "3",
            "debug": "True",
        },
    ),
}


def run_setup(tmp_path, answers, inter=True):
    os.mkdir(tmp_path / "tbot")
    os.symlink(REPO, tmp_path / "tbottest")
    args = ["bash", SCRIPT]
    if inter:
        args.append("--inter")
    return subprocess.run(
        args,
        cwd=tmp_path,
        input="".join(a + "\n" for a in answers),
        capture_output=True,
        text=True,
        timeout=60,
    )


def read_ini(tmp_path, board=BOARD):
    path = tmp_path / "tbotconfig" / board / "tbot.ini"
    cfg = configparser.RawConfigParser(
        interpolation=configparser.ExtendedInterpolation()
    )
    cfg.read(path)
    return cfg, path.read_text()


def read_args(tmp_path, board=BOARD):
    path = tmp_path / "tbotconfig" / board / "args" / f"args{board}"
    return path.read_text().splitlines()


def section(cfg, name):
    return {k: cfg.get(name, k) for k in cfg.options(name)}


def resolve_all(cfg):
    # SSHMACHINE refers to ${usernamessh}, which the template defines in
    # LABHOST only, so it does not resolve; tbottest reads it only for
    # the SSH machine.
    for s in cfg.sections():
        if s != "SSHMACHINE":
            section(cfg, s)


def present(cfg, prefixes, board=BOARD):
    return {p for p in prefixes if cfg.has_section(f"{p}_{board}")}


CONSOLE_PREFIXES = {v[0] for v in CONSOLES.values()}
POWER_PREFIXES = {v[0] for v in POWERS.values()}


@pytest.mark.parametrize(
    "console,power", list(itertools.product(CONSOLES, POWERS))
)
def test_inter_selection(tmp_path, console, power):
    cprefix, canswers, cexpected, cflag = CONSOLES[console]
    pprefix, panswers, pexpected = POWERS[power]

    res = run_setup(
        tmp_path, LAB_ANSWERS + [console] + canswers + [power] + panswers
    )
    assert res.returncode == 0, res.stdout + res.stderr

    cfg, text = read_ini(tmp_path)

    # only the selected console and power control are in the file
    assert present(cfg, CONSOLE_PREFIXES) == {cprefix}
    assert present(cfg, POWER_PREFIXES) == {pprefix}

    # with exactly the values given
    assert section(cfg, f"{cprefix}_{BOARD}") == cexpected
    assert section(cfg, f"{pprefix}_{BOARD}") == pexpected

    # the xmodem example refers to the PICOCOM section
    assert cfg.has_section(f"XMODEM_CONFIG_{BOARD}") == (console == "picocom")

    # every value resolves, as tbottest reads the file
    resolve_all(cfg)

    assert section(cfg, "LABHOST")["labname"] == "testlab"
    assert section(cfg, "LABHOST")["hostname"] == "192.168.1.200"
    assert section(cfg, "LABHOST")["username"] == "labuser"
    assert "BOARDNAME" not in text

    flags = [line for line in read_args(tmp_path) if line.startswith("-f")]
    assert flags == ([cflag] if cflag else [])


def test_ci_defaults(tmp_path):
    res = run_setup(tmp_path, [], inter=False)
    assert res.returncode == 0, res.stdout + res.stderr

    cfg, _ = read_ini(tmp_path, "foo")
    assert present(cfg, CONSOLE_PREFIXES, "foo") == {"PICOCOM"}
    assert present(cfg, POWER_PREFIXES, "foo") == {"SISPMCTRL"}
    assert section(cfg, "PICOCOM_foo") == {
        "baudrate": "115200",
        "device": "/dev/serial/by-id/usb-FTDI_C232HM-EDHSL-0_FT57MR3U-if00-port0",
        "delay": "3",
        "noreset": "True",
    }
    assert section(cfg, "SISPMCTRL_foo") == {"device": "01:01:4f:09:5b", "port": "1"}
    resolve_all(cfg)
    assert read_args(tmp_path, "foo")[1:] == ["-fpicocom"]


@pytest.mark.parametrize(
    "console_inputs,power_inputs,console,power",
    [
        # a unique prefix selects
        (["pi"], ["tm"], "PICOCOM", "TM021"),
        (["k"], ["ti"], "KERMIT", "TF"),
        # empty, ambiguous and unknown input is asked again
        (["", "te"], ["s", "sh"], "TELNET", "POWERSHELLSCRIPT"),
        (["foo", "scriptcom"], ["t", "gpio2", "tbox"], "SCRIPTCOM", "TBOX"),
    ],
)
def test_select_input(tmp_path, console_inputs, power_inputs, console, power):
    cname = next(k for k, v in CONSOLES.items() if v[0] == console)
    pname = next(k for k, v in POWERS.items() if v[0] == power)
    answers = (
        LAB_ANSWERS
        + console_inputs
        + CONSOLES[cname][1]
        + power_inputs
        + POWERS[pname][1]
    )
    res = run_setup(tmp_path, answers)
    assert res.returncode == 0, res.stdout + res.stderr

    cfg, _ = read_ini(tmp_path)
    assert present(cfg, CONSOLE_PREFIXES) == {console}
    assert present(cfg, POWER_PREFIXES) == {power}
    retries = len(console_inputs) + len(power_inputs) - 2
    assert res.stdout.count("not supported") == retries


def test_end_of_input_stops(tmp_path):
    # the input ends at the power control question
    res = run_setup(tmp_path, LAB_ANSWERS + ["picocom"] + CONSOLES["picocom"][1])
    assert res.returncode != 0
    assert "No more input" in res.stderr
