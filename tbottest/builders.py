import tbottest.initconfig as ini
import typing
import pathlib
import tbot
from tbot.machine import linux, connector

cfgt = ini.IniTBotConfig()

_INIT_CACHE: typing.Dict[str, bool] = {}


class genericbuilder(connector.SSHConnector, linux.Bash, linux.Builder):
    def builder_get_sectionname() -> str:
        for f in tbot.flags:
            if "buildername" in f:
                sn = f.split(":")[1]
                sn = f"BUILDHOST_{sn}"
                return sn
        return "BUILDHOST"

    sn = builder_get_sectionname()
    name = cfgt.config_parser.get(sn, "name")
    username = cfgt.config_parser.get(sn, "username")
    hostname = cfgt.config_parser.get(sn, "hostname")
    dl_dir = cfgt.config_parser.get(sn, "dl_dir")
    sstate_dir = cfgt.config_parser.get(sn, "sstate_dir")

    @property
    def kas_ref_dir(self) -> "linux.Path[genericbuilder]":
        kas_ref_dir = cfgt.config_parser.get(self.sn, "kas_ref_dir")
        return linux.Workdir.static(self, kas_ref_dir)

    @property
    def workdir(self) -> "linux.Path[genericbuilder]":
        workdir = cfgt.config_parser.get(self.sn, "workdir")
        return linux.Workdir.static(self, workdir)

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
            try:
                tmp = cfgt.config_parser.get(self.sn, "docker")
                args.append(f"ProxyJump={tmp}")
            except:  # noqa: E722
                pass

        return args

    @property
    def port(self) -> int:
        """
        Return the port the SSH server is listening on.

        :rtype: int
        """
        try:
            port = cfgt.config_parser.get(self.sn, "port")
            return int(port)
        except:
            return 22

    def init(self) -> None:
        if "BHINIT" not in _INIT_CACHE:
            _INIT_CACHE["BHINIT"] = True
            try:
                initcmd = eval(cfgt.config_parser.get(self.sn, "initcmd"))
            except:
                initcmd = []

            for cmd in initcmd:
                c = []
                for t in cmd.split(" "):
                    c.append(t)

                self.exec0(*c)

    @property
    def authenticator(self) -> linux.auth.Authenticator:
        auth = cfgt.config_parser.get(self.sn, "authenticator", fallback=None)
        if auth:
            return linux.auth.PrivateKeyAuthenticator(pathlib.PurePosixPath(auth))

        password = cfgt.config_parser.get(self.sn, "password", fallback=None)
        if password:
            return linux.auth.PasswordAuthenticator(password)

        return linux.auth.NoneAuthenticator()

    def toolchains(self) -> typing.Dict[str, linux.build.Toolchain]:
        raise RuntimeError("toolchains not implemented yet, please add support!")


FLAGS = {
    "buildername": "buildername:<name of builder> searches for BUILDHOST_<name of builder> section if passed to tbot. If not searches for BUILDHOST section",
}
