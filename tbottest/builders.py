import ast
import os
import posixpath
import tbottest.initconfig as ini
import typing
import pathlib
import tbot
from tbot.machine import linux, connector
from tbottest.cmdversions import CmdVersionsMixin

cfgt = ini.IniTBotConfig()

_INIT_CACHE: typing.Dict[str, bool] = {}


def _get_or_placeholder(sn: str, key: str) -> str:
    return cfgt.get_section_config(sn, key, "NOTDEFINED please add BUILDHOST_local in tbot.ini")


class _BuilderPathsMixin:
    """
    kas_ref_dir/workdir/init() are identical between genericbuilder
    and genericbuilderlocal, save for reading self.sn -- shared here
    instead of duplicated on both classes.
    """

    @property
    def kas_ref_dir(self) -> "linux.Path[genericbuilder]":
        kas_ref_dir = cfgt.get_section_config(self.sn, "kas_ref_dir")
        return linux.Workdir.static(self, kas_ref_dir)

    def _relative_base(self) -> str:
        """
        directory a relative workdir or testdir is taken from, the
        directory the shell of the build host starts in; for the local
        build host the directory tbot runs in
        """
        return os.getcwd()

    def _build_host_path(self, path: str) -> str:
        # the build host has POSIX paths; an absolute one stays as it is,
        # without asking the build host for its start directory
        if posixpath.isabs(path):
            return path
        return posixpath.join(self._relative_base(), path)

    @property
    def workdir(self) -> "linux.Path[genericbuilder]":
        workdir = cfgt.get_section_config(self.sn, "workdir")
        return linux.Workdir.static(self, self._build_host_path(workdir))

    @property
    def testdir(self) -> "linux.Path[genericbuilder]":
        """
        directory for what testcases install or build on the build host,
        key testdir, default <workdir>/tbottests; a relative path is taken
        from the same directory as a relative workdir
        """
        testdir = cfgt.get_section_config(self.sn, "testdir", None)
        if not testdir:
            workdir = cfgt.get_section_config(self.sn, "workdir")
            testdir = posixpath.join(workdir, "tbottests")
        return linux.Workdir.static(self, self._build_host_path(testdir))

    def init(self) -> None:
        # cache key is per-class (not a shared literal): genericbuilder
        # and genericbuilderlocal each need their own initcmd run once,
        # independently of each other
        cachekey = type(self).__name__
        if cachekey not in _INIT_CACHE:
            _INIT_CACHE[cachekey] = True
            try:
                initcmd = ast.literal_eval(cfgt.get_section_config(self.sn, "initcmd"))
            except Exception:
                initcmd = []

            for cmd in initcmd:
                c = []
                for t in cmd.split(" "):
                    c.append(t)

                self.exec0(*c)


class genericbuilder(
    CmdVersionsMixin, _BuilderPathsMixin, connector.SSHConnector, linux.Bash, linux.Builder
):
    def builder_get_sectionname() -> str:
        for f in tbot.flags:
            if "buildername" in f:
                sn = f.split(":")[1]
                sn = f"BUILDHOST_{sn}"
                return sn
        return "BUILDHOST"

    sn = builder_get_sectionname()
    _home: typing.Optional[str] = None
    # preset for cmd_get_version(), see tbottest.cmdversions
    cmd_versions_config = cfgt.get_section_config(sn, "cmd_versions", None)
    name = cfgt.get_section_config(sn, "name")
    username = cfgt.get_section_config(sn, "username")
    hostname = cfgt.get_section_config(sn, "hostname")
    dl_dir = cfgt.get_section_config(sn, "dl_dir")
    sstate_dir = cfgt.get_section_config(sn, "sstate_dir")

    @property
    def ssh_config(self) -> typing.List[str]:
        """
        if ProxyJump does not work, execute this command from hand
        on the lab PC with BatchMode=no" -> answer allwith "yes"
        If again password question pops up, copy id_rsa.pub from
        lab PC to authorized_keys on build PC
        """
        args = []
        if "docker" in tbot.flags:
            tmp = cfgt.get_section_config(self.sn, "docker", None)
            if tmp is not None:
                args.append(f"ProxyJump={tmp}")

        return args

    @property
    def port(self) -> int:
        """
        Return the port the SSH server is listening on.

        :rtype: int
        """
        try:
            return int(cfgt.get_section_config(self.sn, "port", 22))
        except ValueError:
            return 22

    @property
    def authenticator(self) -> linux.auth.Authenticator:
        auth = cfgt.get_section_config(self.sn, "authenticator", None)
        if auth:
            return linux.auth.PrivateKeyAuthenticator(pathlib.PurePosixPath(auth))

        password = cfgt.get_section_config(self.sn, "password", None)
        if password:
            return linux.auth.PasswordAuthenticator(password)

        return linux.auth.NoneAuthenticator()

    def _relative_base(self) -> str:
        """
        the home directory of the build host, where its ssh login starts,
        not the directory tbot runs in on this machine; asked once
        """
        if self._home is None:
            self._home = self.env("HOME").strip()
        return self._home

    def toolchains(self) -> typing.Dict[str, linux.build.Toolchain]:
        raise RuntimeError("toolchains not implemented yet, please add support!")


class genericbuilderlocal(
    CmdVersionsMixin,
    _BuilderPathsMixin,
    connector.SubprocessConnector,
    linux.Bash,
    linux.Builder,
):
    sn = "BUILDHOST_local"
    # preset for cmd_get_version(), see tbottest.cmdversions
    cmd_versions_config = cfgt.get_section_config(sn, "cmd_versions", None)
    name = _get_or_placeholder(sn, "name")
    dl_dir = _get_or_placeholder(sn, "dl_dir")
    sstate_dir = _get_or_placeholder(sn, "sstate_dir")

    def toolchains(self) -> typing.Dict[str, linux.build.Toolchain]:
        raise RuntimeError("toolchains not implemented yet, please add support!")


FLAGS = {
    "buildername": (
        "buildername:<name of builder> searches for BUILDHOST_<name of builder> "
        "section if passed to tbot. If not searches for BUILDHOST section. use "
        "name local to build on the machine, on which tbot is started"
    ),
    "docker": "log in to a docker container with proxyjump",
}
