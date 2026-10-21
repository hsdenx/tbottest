"""
configuration and package installation for LinuxShell.cmd_get_version()
of tbot

tbot finds out once per machine which implementation and version a
command has (busybox, procps-ng, ...). The generic machines of tbottest
add two things:

- key ``cmd_versions`` in the ini file presets the results, so tbot does
  not have to find them out on every run (section [LABHOST] or
  [LABHOST_<labname>] in tbot.ini for the lab host, [TC] or
  [TC_<boardname>] in <boardname>.ini for the board). The testcase
  :py:func:`tbottest.tc.common.lnx_cmd_versions` prints such a line,
  :py:func:`tbottest.tc.generic_board.generic_cmd_versions` for the lab
  host and the board.
- ``cmd_get_version(cmd, autoinstall=True)`` installs a missing command on
  Debian, Ubuntu (apt-get) and Fedora (dnf). A Yocto root filesystem has
  no package manager, there the command stays ``notfound``.
"""

import ast
import typing

import tbot

# commands the testcases of tbottest call; the testcase
# lnx_cmd_versions reports these by default
TBOTTEST_COMMANDS = [
    "awk",
    "candump",
    "cangen",
    "dd",
    "devmem",
    "devmem2",
    "ethtool",
    "flash_erase",
    "free",
    "grep",
    "hexdump",
    "i2cdetect",
    "ifconfig",
    "ip",
    "iperf3",
    "ps",
    "sed",
    "tar",
    "top",
]

# Debian package of a command, where the package has another name
# (packages.debian.org, stable); every other command is installed as the
# package of the same name
DEBIAN_PACKAGES = {
    "candump": "can-utils",
    "cangen": "can-utils",
    "free": "procps",
    "flash_erase": "mtd-utils",
    "hexdump": "bsdextrautils",
    "i2cdetect": "i2c-tools",
    "ifconfig": "net-tools",
    "ip": "iproute2",
    "ps": "procps",
    "top": "procps",
}


def cmd_versions_to_config(versions: typing.Dict[str, str], keyindent: str = "") -> str:
    """
    the ini key ``cmd_versions`` for versions, one command per line

    configparser takes a line as continuation of the value if it is
    indented deeper than the key, so the commands are indented by four
    spaces more than the key.

    :param versions: dictionary command -> version string
    :param keyindent: indentation of the key in its section, e.g. four
        spaces in [TC] of the board ini template
    :returns: the lines, starting with ``cmd_versions = {``
    """
    indent = keyindent + "    "
    lines = [f"{keyindent}cmd_versions = {{"]
    lines += [f'{indent}"{k}": "{v}",' for k, v in versions.items()]
    lines.append(f"{indent}}}")
    return "\n".join(lines)


def cmd_versions_from_config(value: typing.Optional[str]) -> typing.Dict[str, str]:
    """
    convert the value of the ini key ``cmd_versions`` into a dictionary

    :param value: python dictionary as string, for example
        ``{"top": "busybox:1.37.0", "ps": "procps-ng:4.0.6"}``; None or an
        empty string give an empty dictionary
    :returns: dictionary command -> version string
    """
    if value is None or value.strip() in ("", "None"):
        return {}
    versions = ast.literal_eval(value)
    if not isinstance(versions, dict):
        raise ValueError(f"cmd_versions is no dictionary: {value}")
    return {str(k): str(v) for k, v in versions.items()}


def os_release_family(osrelease: str) -> str:
    """
    which package manager a system has, from its /etc/os-release

    :param osrelease: content of /etc/os-release
    :returns: "debian" (Debian, Ubuntu and others with ID_LIKE=debian),
        "fedora" (Fedora and ID_LIKE=fedora) or "" for any other system
    """
    ids = []
    for line in osrelease.splitlines():
        key, sep, val = line.partition("=")
        if sep and key.strip() in ("ID", "ID_LIKE"):
            ids += val.strip().strip("\"'").lower().split()
    for family in ("debian", "fedora"):
        if family in ids:
            return family
    return ""


def install_commands(family: str, cmd: str) -> typing.List[typing.List[str]]:
    """
    the commands that install the package of cmd, to be tried one after
    the other until one succeeds

    dnf takes a path as file provide (man dnf5-specs, "File Provides
    matching"), so Fedora needs no table.

    :param family: result of :py:func:`os_release_family`
    :param cmd: the missing command
    :returns: list of argument lists, empty if family is not supported
    """
    if family == "debian":
        return [["apt-get", "-y", "install", DEBIAN_PACKAGES.get(cmd, cmd)]]
    if family == "fedora":
        return [["dnf", "-y", "install", f"{d}/{cmd}"] for d in ("/usr/bin", "/usr/sbin")]
    return []


def install_package(lnx, cmd: str) -> bool:
    """
    install the package that provides cmd on lnx

    :param lnx: linux machine
    :param cmd: the missing command
    :returns: True if an install command succeeded
    """
    # imported here, as tbottest.tc.common imports tbottest.initconfig
    from tbottest.tc.common import lnx_sudo

    ret, out = lnx.exec("cat", "/etc/os-release")
    family = os_release_family(out) if ret == 0 else ""
    cmds = install_commands(family, cmd)
    if not cmds:
        tbot.log.message(
            tbot.log.c(f"cannot install {cmd}, no package manager known on this system").yellow
        )
        return False
    for args in cmds:
        if lnx.exec(*lnx_sudo(lnx), *args)[0] == 0:
            return True
    return False


class CmdVersionsMixin:
    """
    mixin for the linux machines of tbottest, before the tbot shell class

    :py:attr:`cmd_versions_config` is the value of the ini key
    ``cmd_versions``; it is set as preset of cmd_get_version() before the
    first call of cmd_get_version() or cmd_versions_set(), so a value a
    testcase sets wins over the ini file.
    """

    cmd_versions_config: typing.Optional[str] = None

    def _cmd_versions_config_apply(self) -> None:
        if getattr(self, "_cmd_versions_config_done", False):
            return
        self._cmd_versions_config_done = True
        versions = cmd_versions_from_config(self.cmd_versions_config)
        if versions:
            super().cmd_versions_set(versions)  # type: ignore

    def cmd_versions_set(self, versions) -> None:
        self._cmd_versions_config_apply()
        super().cmd_versions_set(versions)  # type: ignore

    def cmd_get_version(self, cmd: str, autoinstall: bool = False, refresh: bool = False):
        self._cmd_versions_config_apply()
        return super().cmd_get_version(cmd, autoinstall, refresh)  # type: ignore

    def install_package(self, cmd: str) -> bool:
        return install_package(self, cmd)
