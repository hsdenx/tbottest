"""
Command line completion of modules and testcases for newtbot_starter.py.

tbot completes ``module.function`` by looking the module path up as
directories below the working directory.  In a setup made by
create_setup.sh the package tbottest is tbottest/tbottest below it,
because newtbot_starter.py puts the tbottest repository into sys.path,
so tbot finds nothing for ``tbottest.tc.<TAB>`` (or ``$tbtc.<TAB>``).
These functions look a dotted module path up as an import does, through
sys.path, and replace the ones of tbot.newbot; the working directory
stays the setup, so the board configuration with its relative paths
still loads when a module is imported to list its testcases.

This file must not import the tbottest package, because
tbottest/__init__.py looks at the tbot flags when it is imported, and
here tbot has not set them yet.
"""

import importlib
import importlib.util
import itertools
import pathlib
import typing


def _find_spec(modpath: str) -> typing.Any:
    """the module spec of modpath, None if there is no such module"""
    try:
        return importlib.util.find_spec(modpath)
    except (ImportError, ValueError):
        return None


def module_dirs(modpath: str) -> typing.List[pathlib.Path]:
    """
    The directories which hold the submodules of the package modpath, as
    an import finds them.  Top-level modules ("" for modpath) are only
    looked for in the working directory, as tbot does, so the standard
    library does not show up.
    """
    if modpath == "":
        return [pathlib.Path(".")]
    spec = _find_spec(modpath)
    if spec is None or spec.submodule_search_locations is None:
        return []
    return [pathlib.Path(p) for p in spec.submodule_search_locations]


def complete_module(cur: str) -> typing.Iterable[str]:
    """the module paths that complete cur, as tbot.newbot.complete_module()"""
    # the parameters of the testcase follow, nothing to complete
    if ":" in cur:
        return ()

    components = cur.rsplit(".", 1)
    if len(components) == 2:
        modpath = components[0] + "."
        frag = components[1]
    else:
        modpath = ""
        frag = components[0]

    dirs = [d for d in module_dirs(modpath.rstrip(".")) if d.is_dir()]

    # complete inside a package the fragment names already, as if a
    # trailing "." was given
    if frag != "" and any((d / frag).is_dir() for d in dirs):
        return complete_module(modpath + frag + ".")

    # subdirectories and python files are module names
    candidates = set()
    for path in dirs:
        for child in path.iterdir():
            if child.name.startswith(frag) and not child.name.startswith("__"):
                if child.is_dir():
                    candidates.add(child.name)
                elif child.is_file() and child.suffix == ".py":
                    candidates.add(child.stem)

    return (modpath + c for c in sorted(candidates))


def complete_testcase(cur: str) -> typing.Iterable[str]:
    """
    the testcases and module paths that complete cur, as
    tbot.newbot.complete_testcase()
    """
    # the parameters of the testcase follow, nothing to complete
    if ":" in cur:
        return ()

    components = cur.rsplit(".", 1)
    if len(components) == 1:
        return complete_module(cur)

    modpath, frag = components
    if frag != "":
        spec = _find_spec(modpath + "." + frag)
        if spec is not None and spec.submodule_search_locations is None:
            modpath += "." + frag
            frag = ""

    spec = _find_spec(modpath)
    if spec is None:
        return complete_module(cur)

    module = importlib.import_module(modpath)
    callables = (f for f in dir(module) if callable(getattr(module, f, None)))
    matching = (modpath + "." + f for f in callables if f.startswith(frag))

    if spec.submodule_search_locations is not None:
        return itertools.chain(complete_module(cur), matching)
    return matching


def install(newbot: typing.Any) -> None:
    """replace the completion functions of the module tbot.newbot"""
    newbot.complete_module = complete_module
    newbot.complete_testcase = complete_testcase
