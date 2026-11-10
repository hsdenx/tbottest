"""
Testcases around /etc/buildinfo.

image-buildinfo of OpenEmbedded writes into every image the values of
IMAGE_BUILDINFO_VARS and the revision of every layer it was built from. A
test on the board can read them back and see whether it runs the build it
is meant to test: a variable that names the build, set once per build, and
the commits of the layers that build was made from.

Generic: which variables and layers to check, and what they should say, is
handed in.
"""

import typing
import tbot
from tbot.machine import linux

BUILDINFO_FILE = "/etc/buildinfo"


def buildinfo_parse(text: str) -> typing.Tuple[dict, dict]:
    """
    the variables and the layer revisions of a /etc/buildinfo

    A variable that is listed twice gets the value of its last line.

    :param text: content of /etc/buildinfo
    :returns: (variables, layers); variables maps name to value, layers
        maps name to {"branch": .., "revision": .., "modified": True or
        False}
    """
    variables = {}
    layers = {}
    section = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Build Configuration:"):
            section = "vars"
            continue
        if stripped.startswith("Layer Revisions:"):
            section = "layers"
            continue
        if "=" not in line or section is None:
            continue

        # an empty value leaves no blank after the =
        name, _, value = line.partition("=")
        name = name.strip()
        value = value.strip()
        if section == "vars":
            variables[name] = value
            continue

        modified = value.endswith("-- modified")
        if modified:
            value = value[: -len("-- modified")].strip()
        branch, _, revision = value.rpartition(":")
        layers[name] = {"branch": branch, "revision": revision, "modified": modified}

    return variables, layers


def buildinfo_compare(
    variables: dict, layers: dict, expected_vars: dict, expected_layers: dict
) -> list:
    """
    what of a parsed /etc/buildinfo differs from what is expected

    A layer revision counts as matching when the one in the file starts
    with the expected one, so a short commit ID will do. A layer built
    from a modified checkout does not match.

    :param variables: variables, see buildinfo_parse()
    :param layers: layers, see buildinfo_parse()
    :param expected_vars: variable name to expected value
    :param expected_layers: layer name to expected revision
    :returns: list of messages, empty when everything matches
    """
    failed = []
    for name, want in expected_vars.items():
        got = variables.get(name)
        if got is None:
            failed.append(f"{name} is not in the buildinfo")
        elif got != want:
            failed.append(f"{name} = {got}, expected {want}")

    for name, want in expected_layers.items():
        layer = layers.get(name)
        if layer is None:
            failed.append(f"layer {name} is not in the buildinfo")
        elif not want or not layer["revision"].startswith(want):
            failed.append(f"layer {name} at {layer['revision']}, expected {want}")
        elif layer["modified"]:
            failed.append(f"layer {name} was built from a modified checkout")

    return failed


@tbot.testcase
def lnx_check_buildinfo(
    lnx: linux.LinuxShell,
    expected_vars: typing.Optional[dict] = None,
    expected_layers: typing.Optional[dict] = None,
    path: str = BUILDINFO_FILE,
) -> bool:
    """
    check /etc/buildinfo on the board against what the build should be

    Logs every layer revision found, and every difference.

    :param lnx: board linux machine
    :param expected_vars: variable name to expected value
    :param expected_layers: layer name to expected revision, a short
        commit ID will do
    :param path: path of the buildinfo file on the board
    :returns: True if everything matches
    """
    ret, text = lnx.exec("cat", path)
    if ret != 0:
        tbot.log.message(tbot.log.c(f"no {path} on the board").red)
        return False

    variables, layers = buildinfo_parse(text)
    for name, layer in layers.items():
        tbot.log.message(f"layer {name}: {layer['branch']}:{layer['revision']}")

    failed = buildinfo_compare(variables, layers, expected_vars or {}, expected_layers or {})
    for msg in failed:
        tbot.log.message(tbot.log.c(msg).red)
    if not failed:
        tbot.log.message(tbot.log.c(f"{path} is the build expected").green)
    return not failed
