"""
Unit tests for tbottest/tc/kas.py's KAS.__init__ config-field
extraction (required fields, optional fields with defaults, and the
buildtargets/resultimages "stay unset if absent" special case).
"""

import os

import pytest

from conftest import load_module

kas = load_module(
    "tbottest_tc_kas",
    os.path.join(os.path.dirname(__file__), "..", "tbottest", "tc", "kas.py"),
)


class FakeHost:
    """Stands in for the buildhost; the kas-source-download try/except
    in KAS.__init__ is expected to fail against this (no real
    workdir/exec0) and fall back to "use the installed kas command"."""

    workdir = kas.linux.Path("/work/bh")

    def exec0(self, *a, **kw):
        raise RuntimeError("no real host in this test")

    def exec(self, *a, **kw):
        return (1, "")


def base_cfg(**overrides):
    cfg = {
        "labhost": object(),
        "buildhost": FakeHost(),
        "build_machine": "scale",
        "subdir": "toptica/scale",
        "kaslayer": "kas-toptica",
        "kaslayerbranch": "main",
        "kasconfigfile": "toptica.yml",
    }
    cfg.update(overrides)
    return cfg


REQUIRED_FIELDS = [
    ("labhost", "please define labhost"),
    ("buildhost", "please define buildhost"),
    ("build_machine", "please define build_machine"),
    ("subdir", "please configure subdir"),
    ("kaslayer", "please configure kaslayer"),
    ("kaslayerbranch", "please configure kaslayerbranch"),
    ("kasconfigfile", "please configure kasconfigfile"),
]


class TestRequiredFields:
    @pytest.mark.parametrize("missing_key,message", REQUIRED_FIELDS)
    def test_missing_required_field_raises(self, missing_key, message):
        cfg = base_cfg()
        del cfg[missing_key]
        with pytest.raises(RuntimeError, match=message):
            kas.KAS(cfg)

    def test_all_required_fields_present_succeeds(self):
        obj = kas.KAS(base_cfg())
        assert obj.build_machine == "scale"
        assert obj.subdir == "toptica/scale"
        assert obj.kaslayer == "kas-toptica"
        assert obj.kaslayerbranch == "main"
        assert obj.kasconfigfile == "toptica.yml"


class TestOptionalFields:
    def test_defaults_when_absent(self):
        obj = kas.KAS(base_cfg())
        assert obj.container is False
        assert obj.container_engine is None
        assert obj.git_credential_store is None
        assert obj.netrc_file is None
        assert obj.kas_runtime_args is None
        assert obj.kas_ssh_dir is None
        assert obj.deploypath is None
        assert obj.kaslayername is None
        assert obj.bitbakeenvinit == "sources/poky/oe-init-build-env"
        assert obj.bitbakeoptions == []
        assert obj.envinit is None
        assert obj.autoconf is None

    def test_overrides_when_present(self):
        obj = kas.KAS(
            base_cfg(
                kascontainer=True,
                kascontainerengine="podman",
                git_credential_store="/home/x/.git-credentials",
                netrc_file="/home/x/.netrc",
                kas_runtime_args="--foo",
                ssh_dir="/home/x/.ssh",
                deploypath="custom/deploy",
                kaslayername="mylayer",
                bitbakeenvinit="custom-env-init",
                bitbakeoptions=["-q", "-q"],
                envinit=["export X=1"],
            )
        )
        assert obj.container is True
        assert obj.container_engine == "podman"
        assert obj.git_credential_store == "/home/x/.git-credentials"
        assert obj.netrc_file == "/home/x/.netrc"
        assert obj.kas_runtime_args == "--foo"
        assert obj.kas_ssh_dir == "/home/x/.ssh"
        assert obj.deploypath == "custom/deploy"
        assert obj.kaslayername == "mylayer"
        assert obj.bitbakeenvinit == "custom-env-init"
        assert obj.bitbakeoptions == ["-q", "-q"]
        assert obj.envinit == ["export X=1"]


class TestBuildtargetsResultimagesStayUnset:
    """
    Unlike the other optional fields, these two must stay *unset*
    (not defaulted to None) when absent from cfg, so that
    kas_build()/kas_copy() can tell "not configured" apart from
    "configured as empty" via AttributeError and raise a clear
    RuntimeError instead of a confusing "'NoneType' is not iterable".
    """

    def test_stay_unset_when_absent(self):
        obj = kas.KAS(base_cfg())
        assert not hasattr(obj, "buildtargets")
        assert not hasattr(obj, "resultimages")

    def test_set_when_present(self):
        obj = kas.KAS(base_cfg(buildtargets=["core-image"], resultimages=["foo.wic"]))
        assert obj.buildtargets == ["core-image"]
        assert obj.resultimages == ["foo.wic"]

    def test_kas_build_raises_clear_error_when_unset(self):
        obj = kas.KAS(base_cfg())
        with pytest.raises(RuntimeError, match="please specify buildtargets"):
            obj.kas_build()

    def test_kas_copy_raises_clear_error_when_unset(self):
        obj = kas.KAS(base_cfg())
        with pytest.raises(RuntimeError, match="please specify buildtargets"):
            obj.kas_copy()
