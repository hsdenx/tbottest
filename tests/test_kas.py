"""
Unit tests for tbottest/tc/kas.py's KAS.__init__ config-field
extraction (required fields, optional fields with defaults, and the
buildtargets/resultimages "stay unset if absent" special case).
"""

import os
import sys

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
        "build_machine": "MACHINE",
        "subdir": "VENDOR/BOARDNAME",
        "kaslayer": "kas-BOARDNAME",
        "kaslayerbranch": "main",
        "kasconfigfile": "BOARDNAME.yml",
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
        assert obj.build_machine == "MACHINE"
        assert obj.subdir == "VENDOR/BOARDNAME"
        assert obj.kaslayer == "kas-BOARDNAME"
        assert obj.kaslayerbranch == "main"
        assert obj.kasconfigfile == "BOARDNAME.yml"


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


class TestKasMounts:
    def test_default_is_no_mount(self):
        assert kas.KAS(base_cfg()).kas_mounts == []

    def test_mounts_are_taken_over(self):
        obj = kas.KAS(base_cfg(kas_mounts=["/h/scripts:/scripts:ro"]))
        assert obj.kas_mounts == ["/h/scripts:/scripts:ro"]

    def test_mount_without_colon_raises(self):
        with pytest.raises(RuntimeError, match="not host:container"):
            kas.KAS(base_cfg(kas_mounts=["/h/scripts"]))


class TestRuntimeArgsWithMounts:
    def test_nothing_configured_gives_none(self):
        assert kas.kas_runtime_args_with_mounts(None, []) is None
        assert kas.kas_runtime_args_with_mounts('""', None) is None

    def test_runtime_args_alone_keep_their_value(self):
        assert kas.kas_runtime_args_with_mounts('"--privileged"', []) == '"--privileged"'

    def test_runtime_args_without_quotes_get_quoted(self):
        assert kas.kas_runtime_args_with_mounts("--privileged", []) == '"--privileged"'

    def test_mounts_are_appended_inside_the_quotes(self):
        got = kas.kas_runtime_args_with_mounts(
            '"--privileged -v /dl:/downloads"', ["/h/scripts:/scripts:ro", "/a:/b"]
        )
        assert got == '"--privileged -v /dl:/downloads -v /h/scripts:/scripts:ro -v /a:/b"'

    def test_mounts_alone(self):
        got = kas.kas_runtime_args_with_mounts(None, ["/h/scripts:/scripts"])
        assert got == '"-v /h/scripts:/scripts"'


class TestKeepConfig:
    """tbot flag kaskeepconfig, like kas --keep-config-unchanged"""

    @pytest.fixture
    def flags(self, monkeypatch):
        tbot = sys.modules["tbot"]
        monkeypatch.setattr(tbot, "flags", set())
        return tbot.flags

    def test_without_flag_no_extra_option(self, flags):
        obj = kas.KAS(base_cfg())
        assert obj.keep_config is False
        assert obj.kas_keep_config_args() == []

    def test_with_flag_passes_keep_config_unchanged(self, flags):
        flags.add("kaskeepconfig")
        obj = kas.KAS(base_cfg())
        assert obj.keep_config is True
        assert obj.kas_keep_config_args() == ["--keep-config-unchanged"]

    def test_with_flag_checkout_touches_nothing(self, flags):
        # FakeHost.exec0 raises, so any pull, kas checkout or auto.conf
        # write would fail this test
        flags.add("kaskeepconfig")
        kas.KAS(base_cfg()).kas_checkout()

    def test_without_flag_checkout_does_work(self, flags):
        with pytest.raises(RuntimeError, match="no real host"):
            kas.KAS(base_cfg()).kas_checkout()


class TestCheckoutLayerBranch:
    """kas_checkout() puts the kas layer on kaslayerbranch, also in an
    existing clone"""

    class Host(FakeHost):
        def __init__(self, clone_exists):
            self.clone_exists = clone_exists
            self.cmds = []

        def test(self, *a, **kw):
            return self.clone_exists

        def exec0(self, *a, **kw):
            self.cmds.append([str(x) for x in a])
            return ""

    @pytest.fixture(autouse=True)
    def flags(self, monkeypatch):
        monkeypatch.setattr(sys.modules["tbot"], "flags", set())

    def git_cmds(self, host):
        return [c for c in host.cmds if c[0] == "git"]

    def checkout(self, host):
        kas.KAS(
            base_cfg(
                buildhost=host, kaslayername="kas-BOARDNAME", kaslayerbranch="feature/xyz"
            )
        ).kas_checkout()

    def test_existing_clone_is_switched_to_the_branch(self):
        host = self.Host(clone_exists=True)
        self.checkout(host)
        assert self.git_cmds(host) == [
            ["git", "-C", "kas-BOARDNAME", "fetch", "origin", "feature/xyz"],
            ["git", "-C", "kas-BOARDNAME", "checkout", "-B", "feature/xyz", "FETCH_HEAD"],
        ]

    def test_missing_clone_is_cloned_with_the_branch(self):
        host = self.Host(clone_exists=False)
        self.checkout(host)
        assert self.git_cmds(host) == [
            ["git", "clone", "kas-BOARDNAME", "-b", "feature/xyz", " kas-BOARDNAME"],
        ]

    def test_without_kaslayername_the_dir_comes_from_the_url(self):
        host = self.Host(clone_exists=True)
        kas.KAS(
            base_cfg(buildhost=host, kaslayer="https://example.com/kas-BOARDNAME.git")
        ).kas_checkout()
        assert self.git_cmds(host)[0][:3] == ["git", "-C", "kas-BOARDNAME"]

    def test_missing_branch_fails(self):
        class Host(self.Host):
            def exec0(self, *a, **kw):
                if "fetch" in a:
                    raise RuntimeError("couldn't find remote ref")
                return super().exec0(*a, **kw)

        with pytest.raises(RuntimeError, match="remote ref"):
            kas.KAS(base_cfg(buildhost=Host(clone_exists=True))).kas_checkout()


class TestKasUpdate:
    """tbot flag kasupdate, like kas --update"""

    @pytest.fixture
    def flags(self, monkeypatch):
        tbot = sys.modules["tbot"]
        monkeypatch.setattr(tbot, "flags", set())
        return tbot.flags

    def kas_checkout_cmd(self):
        host = TestCheckoutLayerBranch.Host(clone_exists=True)
        kas.KAS(base_cfg(buildhost=host)).kas_checkout()
        return [c for c in host.cmds if "checkout" in c and c[0] == "kas"][0]

    def test_without_flag_no_extra_option(self, flags):
        assert kas.KAS(base_cfg()).kas_update_args() == []
        assert "--update" not in self.kas_checkout_cmd()

    def test_with_flag_passes_update(self, flags):
        flags.add("kasupdate")
        assert kas.KAS(base_cfg()).kas_update_args() == ["--update"]
        assert self.kas_checkout_cmd()[1:] == [
            "checkout",
            "--update",
            "/work/bh/VENDOR/BOARDNAME/kasconfig/BOARDNAME.yml",
        ]

    def test_kaskeepconfig_wins(self, flags):
        flags.add("kasupdate")
        flags.add("kaskeepconfig")
        assert kas.KAS(base_cfg()).kas_update_args() == []


class TestKasBuildDir:
    """kas_build_dir: own build directory, passed as KAS_BUILD_DIR"""

    class Host(FakeHost):
        # kas_get_basepath() creates its workdir with exec0
        def exec0(self, *a, **kw):
            return ""

    def test_default_is_build(self):
        obj = kas.KAS(base_cfg())
        assert obj.kas_build_dir is None
        assert obj.buildsubpath == "build"
        assert obj.kas_build_dir_env() == []

    def test_build_dir_sets_buildpath_and_env(self):
        obj = kas.KAS(base_cfg(buildhost=self.Host(), kas_build_dir="build-musl"))
        assert obj.buildsubpath == "build-musl"
        assert obj.kas_get_buildpath()._local_str() == "/work/bh/VENDOR/BOARDNAME/build-musl"
        env = obj.kas_build_dir_env()
        assert [str(e) for e in env] == [
            'KAS_BUILD_DIR="/work/bh/VENDOR/BOARDNAME/build-musl"'
        ]

    def test_deploypath_is_below_the_build_dir(self):
        obj = kas.KAS(
            base_cfg(
                buildhost=self.Host(),
                kas_build_dir="build-glibc",
                deploypath="deploy-glibc/images/MACHINE",
            )
        )
        assert obj.kas_get_deploypath()._local_str() == (
            "/work/bh/VENDOR/BOARDNAME/build-glibc/deploy-glibc/images/MACHINE"
        )


class TestGroupTargets:
    def test_plain_targets_in_one_call(self):
        assert kas.kas_group_targets(["image", "firmware-swu", "rescue-swu"]) == [
            "image firmware-swu rescue-swu"
        ]

    def test_command_lines_stay_calls_of_their_own_in_place(self):
        targets = ["core-image", "DISTRO=poky-rescue bitbake rescueimage-fit", "swu-image", "swu2"]
        assert kas.kas_group_targets(targets) == [
            "core-image",
            "DISTRO=poky-rescue bitbake rescueimage-fit",
            "swu-image swu2",
        ]

    def test_empty(self):
        assert kas.kas_group_targets([]) == []


class TestBuildCalls:
    """kas_build() with the container, as the CI uses it"""

    class Host(TestCheckoutLayerBranch.Host):
        def __init__(self):
            super().__init__(clone_exists=True)

    @pytest.fixture(autouse=True)
    def flags(self, monkeypatch):
        monkeypatch.setattr(sys.modules["tbot"], "flags", set())
        return sys.modules["tbot"].flags

    def kas_obj(self, host, **cfg):
        k = kas.KAS(base_cfg(buildhost=host, **cfg))
        k.container = True
        k.kascmd = "kas-container"
        return k

    def test_targets_in_one_kas_build(self):
        host = self.Host()
        self.kas_obj(host, buildtargets=["image", "rescue-fit", "full-swu"]).kas_build()
        builds = [c for c in host.cmds if "kas-container" in c]
        assert len(builds) == 1
        assert "KAS_TARGET='image rescue-fit full-swu'" in builds[0]
        assert "KAS_TASK=build" in builds[0]

    def test_target_with_c_in_its_name_is_no_task(self):
        # "-c" inside a name, followed by a second target in the same call
        host = self.Host()
        self.kas_obj(host, buildtargets=["linux-cxx", "image"]).kas_build()
        build = [c for c in host.cmds if "kas-container" in c][0]
        assert "KAS_TARGET='linux-cxx image'" in build
        assert "KAS_TASK=build" in build


class TestSiteConf:
    class Host(TestCheckoutLayerBranch.Host):
        def __init__(self):
            super().__init__(clone_exists=True)

    @pytest.fixture(autouse=True)
    def flags(self, monkeypatch):
        monkeypatch.setattr(sys.modules["tbot"], "flags", set())
        return sys.modules["tbot"].flags

    LINES = ['MY_BUILD_ID = "1234"', 'OTHER = "x"']

    def siteconf_writes(self, host):
        return [c for c in host.cmds if c and c[-1].endswith("conf/site.conf")]

    def test_written_anew_on_checkout(self):
        host = self.Host()
        kas.KAS(base_cfg(buildhost=host, **{"site.conf": self.LINES})).kas_checkout()
        writes = self.siteconf_writes(host)
        assert [w[:3] for w in writes] == [
            ["echo", self.LINES[0], ">"],
            ["echo", self.LINES[1], ">>"],
        ]

    def test_written_anew_on_build(self):
        host = self.Host()
        k = kas.KAS(base_cfg(buildhost=host, buildtargets=["image"], **{"site.conf": self.LINES}))
        k.container = True
        k.kas_build()
        assert [w[2] for w in self.siteconf_writes(host)] == [">", ">>"]

    def test_nothing_without_key(self):
        host = self.Host()
        kas.KAS(base_cfg(buildhost=host)).kas_checkout()
        assert self.siteconf_writes(host) == []

    def test_kaskeepconfig_leaves_it(self, flags):
        flags.add("kaskeepconfig")
        host = self.Host()
        kas.KAS(base_cfg(buildhost=host, **{"site.conf": self.LINES})).kas_checkout()
        assert self.siteconf_writes(host) == []


class TestContainerCheckout:
    """kas_checkout() with kas-container, as the CI uses it"""

    class Host(TestCheckoutLayerBranch.Host):
        def __init__(self):
            super().__init__(clone_exists=True)

    @pytest.fixture(autouse=True)
    def flags(self, monkeypatch):
        monkeypatch.setattr(sys.modules["tbot"], "flags", set())
        return sys.modules["tbot"].flags

    def checkout_cmd(self, host, **cfg):
        k = kas.KAS(base_cfg(buildhost=host, **cfg))
        k.container = True
        k.kascmd = "kas-container"
        k.kas_checkout()
        cmds = [c for c in host.cmds if "kas-container" in c]
        assert len(cmds) == 1
        return cmds[0]

    def test_container_checks_out(self):
        cmd = self.checkout_cmd(self.Host())
        assert cmd[cmd.index("kas-container") + 1:] == [
            "checkout",
            "/work/bh/VENDOR/BOARDNAME/kasconfig/BOARDNAME.yml",
        ]

    def test_container_checkout_with_kasupdate(self, flags):
        flags.add("kasupdate")
        cmd = self.checkout_cmd(self.Host())
        assert cmd[cmd.index("checkout") + 1] == "--update"

    def test_container_checkout_gets_the_credentials_of_the_build(self):
        cmd = self.checkout_cmd(
            self.Host(), git_credential_store="/home/u/.git-credentials", netrc_file="/home/u/.netrc"
        )
        assert "NETRC_FILE=/home/u/.netrc" in cmd
        i = cmd.index("--git-credential-store")
        assert cmd[i + 1] == "/home/u/.git-credentials"
        assert i < cmd.index("checkout")
