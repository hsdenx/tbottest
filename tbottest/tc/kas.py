import tbot
from tbot.machine import linux
from tbot.tc.shell import copy as shell_copy


class KAS:
    """
    helper class for building yocto projects with kas

    | url: https://github.com/siemens/kas
    | doc: https://kas.readthedocs.io/en/latest/

    example:

    .. code-block:: python

        from kas import KAS

        cfgkas = {
            "kasurl" : "url from where kas sources get downloaded",
            "kasversion" : "kas version",
            "build_machine" : "machinename",
            "subdir" : "temp/customer",
            "kascontainer" : True,
            "netrc_file" : "path to .netrc file, sets NETRC_FILE",
            "git_credential_store" : "/home/<username>/.git-credentials",
            "ssh_dir" : "/home/<username>/.ssh",
            "kaslayer" : "192.168.1.107:<path_to_kasconfig_layer>",
            "kaslayername" : "name_of_repo",
            "kaslayerbranch" : "dunfell",
            "kasconfigfile" : "<pathto>/kas-machinename-denx.yml",
            "bitbakeenvinit" : "sources/poky/oe-init-build-env",
            "envinit" : [""],
            "buildtargets" : ["core-image", "rescueimage-fit", "swu-image"]
            "bitbakeoptions" : ["-q -q"]
        }


    kasurl

    if you need (or want) to download kas sources from an url, set this.

    You do not need to install kas from this sources, as this class simply
    use **run-kas** script from within the kas sources.

    kasversion

    kas version which get checkedout, when you download kas

    build_machine

    machine name which is used for the build

    subdir

    based on the build machines workdir, kas sources get checkout into
    **subdir**

    kas-container

    to build with kas-container script set kascontainer to True
    You may need to pass **--git-credential-store** to the kas-container script.
    Set this through:

       git_credential_store

    You may need to pass **--ssh-dir** to the kas-container script. Set this
    Set this through:

        ssh_dir

    You may need to pass a .netrc file, so set the kas environment varaible
    NETRC_FILE.

    Set this through:

        netrc_file

    You may want to set the used container engine through **KAS_CONTAINER_ENGINE**
    Set this through:

       kascontainerengine

    You may want to add "--runtime-args" to kas-container, so set

        kas_runtime_args

    example:

    .. code-block:: python

        "kas_runtime_args" : '\"-v /work/hs/yocto/download:/workdownload\"',

    You need the ```"``` so escape them!

    kaslayer

    sources which contain your kas config file(s). This class downloads them
    into kas_get_basepath / "kasconfig"

    kaslayername

    you can give them an unique name

    kaslayerbranch

    branch which is used

    kasconfigfile

    kas config file which is used

    auto.conf

    You can define here an auto.conf file, if you need to add
    special settings. The file is created after kas_checkout
    ends.

    .. code-block:: python

       "auto.conf" : ['DL_DIR="/workdownload"',
                     'SSTATE_DIR="/worksstate-cache"',
           ],

    bitbakeenvinit

    if you are not using a kas container you need to source the oe environment
    script (and may have to setup more stuff) before you can call bitbake. This
    entry contains a list of commandstrings, which are executed when kas
    has checkout the source code. Default is "sources/poky/oe-init-build-env"

    envinit

    Here you can add additional commands you need, when you build in kas-container

    _`buildtargets`

    array of strings containing the names of the build targets with which bitbake
    is called.

    If string "bitbake" is in buildtargets, bitbake command is not added
    to command.

    For example you can write

    .. code-block:: python

        "buildtargets" : ["core-image", "DISTRO=poky-rescue bitbake rescueimage-fit", "swu-image"]

    which will result in the following bitbake calls

    .. code-block:: bash

        $ bitbake core-image
        $ DISTRO=poky-rescue bitbake rescueimage-fit
        $ bitbake rescueimage-fit
        $ bitbake swu-image


    bitbakeoptions

    options with which bitbake is called (for example you may want to pass -q)
    So with above setting:

    .. code-block:: python

        "bitbakeoptions" : ["-q -q"]

    you get the bitbake calls:

    .. code-block:: bash

        $ bitbake -q -q core-image
        $ DISTRO=poky-rescue bitbake rescueimage-fit
        $ bitbake -q -q rescueimage-fit
        $ bitbake -q -q swu-image

    """

    def __init__(self, cfg: dict) -> None:  # noqa: D107
        self.cfg = cfg
        self.env_inited = False
        self.buildsubpath = "build"
        self.bitbakeoptions = []
        self.kascmd = "kas"
        self.kaspath = None
        self.netrc_file = None
        self.git_credential_store = None
        self.kas_runtime_args = None
        self.kas_ssh_dir = None
        self.container_engine = None
        self.container = False
        self.kasconfigpath = None
        self.autoconf = None

        try:
            self.lab = self.cfg["labhost"]
        except:  # noqa: E722
            raise RuntimeError("please define labhost")

        try:
            self.bh = self.cfg["buildhost"]
        except:  # noqa: E722
            raise RuntimeError("please define buildhost")

        try:
            self.container = self.cfg["kascontainer"]
        except:  # noqa: E722
            pass

        try:
            self.container_engine = self.cfg["kascontainerengine"]
        except:  # noqa: E722
            pass

        try:
            self.git_credential_store = self.cfg["git_credential_store"]
        except:  # noqa: E722
            pass

        try:
            self.netrc_file = self.cfg["netrc_file"]
        except:  # noqa: E722
            pass

        try:
            self.kas_runtime_args = self.cfg["kas_runtime_args"]
        except:  # noqa: E722
            pass

        try:
            self.kas_ssh_dir = self.cfg["ssh_dir"]
        except:  # noqa: E722
            pass

        try:
            self.kasurl = self.cfg["kasurl"]
            self.kas_version = self.cfg["kasversion"]
            self.kaspath = linux.Workdir.static(self.bh, self.bh.workdir / "kasdownload")
            self.bh.exec0("cd", self.kaspath._local_str())
            self.bh.exec(
                "git",
                "-C",
                "kas",
                "pull",
                linux.Raw("||"),
                "git",
                "clone",
                self.kasurl,
            )
            if self.kas_version:
                self.bh.exec0("cd", "kas")
                self.bh.exec0("git", "checkout", self.kas_version)
                self.bh.exec0("cd", "..")

            if self.container:
                self.kascmd = f"{self.kaspath._local_str()}/kas/kas-container"
            else:
                self.kascmd = f"{self.kaspath._local_str()}/kas/run-kas"
        except:  # noqa: E722
            # simply use the installed kas command
            pass

        try:
            self.build_machine = self.cfg["build_machine"]
        except:  # noqa: E722
            raise RuntimeError("please define build_machine")

        try:
            self.subdir = self.cfg["subdir"]
        except:  # noqa: E722
            raise RuntimeError("please configure subdir")

        try:
            self.kaslayer = self.cfg["kaslayer"]
        except:  # noqa: E722
            raise RuntimeError("please configure kaslayer")

        try:
            self.kaslayername = self.cfg["kaslayername"]
        except:  # noqa: E722
            self.kaslayername = None

        try:
            self.kaslayerbranch = self.cfg["kaslayerbranch"]
        except:  # noqa: E722
            raise RuntimeError("please configure kaslayerbranch")

        try:
            self.kasconfigfile = self.cfg["kasconfigfile"]
        except:  # noqa: E722
            raise RuntimeError("please configure kasconfigfile")

        try:
            self.bitbakeenvinit = self.cfg["bitbakeenvinit"]
        except:  # noqa: E722
            self.bitbakeenvinit = "sources/poky/oe-init-build-env"

        # optional setting
        try:
            self.bitbakeoptions = self.cfg["bitbakeoptions"]
        except:  # noqa: E722
            pass

        try:
            self.buildtargets = self.cfg["buildtargets"]
        except:  # noqa: E722
            pass

        try:
            self.resultimages = self.cfg["resultimages"]
        except:  # noqa: E722
            pass

        try:
            self.envinit = self.cfg["envinit"]
        except:
            self.envinit = None

        try:
            self.autoconf = self.cfg["auto.conf"]
        except:
            self.autoconf = None

        self.kasconfigpath = self.kas_get_basepath() / "kasconfig"

    @tbot.testcase
    def kas_get_basepath(self) -> linux.Path:
        """
        get the basepath where kas works in at your build host

        .. code-block:: python

            @tbot.testcase
            def try_kas_getbasepath(
                lab: Optional[linux.LinuxShell] = None,
                bh: Optional[linux.LinuxShell] = None,
            ):
                with tbot.ctx() as cx:
                    if lab is None:
                        lab = cx.request(tbot.role.LabHost)

                    if bh is None:
                        bh = cx.request(tbot.role.BuildHost)

                    cfgkas["labhost"] = lab
                    cfgkas["buildhost"] = bh

                    kas = KAS(cfgkas)
                    val = kas.kas_get_basepath()
        """
        return linux.Workdir.static(self.bh, self.bh.workdir / self.subdir)

    @tbot.testcase
    def kas_get_buildpath(self) -> linux.Path:
        """
        get the build path kas uses
        """
        # we do not want to create this path
        # this is done through yocto setup
        return self.kas_get_basepath() / self.buildsubpath

    @tbot.testcase
    def kas_get_deploypath(self) -> linux.Path:
        """
        get the deploypath kas uses
        """
        # we do not want to create this path
        # this is done through yocto setup
        return self.kas_get_buildpath() / f"tmp/deploy/images/{self.build_machine}"

    @tbot.testcase
    def kas_env_init(self):
        if self.container:
            return

        if self.env_inited is False:
            path = self.kas_get_basepath()
            self.bh.exec0("cd", path)
            self.bh.exec0("source", self.bitbakeenvinit, self.buildsubpath)
            if self.envinit:
                for env in self.envinit:
                    self.bh.exec0(linux.Raw(env))

    def kas_create_autoconf(self) -> None:
        if self.autoconf:
            bp = self.kas_get_buildpath()
            cfgp = bp / "conf"
            ret, log = self.bh.exec("ls", "-al", cfgp / "auto.conf")
            if ret == 0:
                tbot.log.message("auto.conf exists, do not create it")
                return 0

            op = linux.Raw(">")
            self.bh.exec0("mkdir", "-p", cfgp)
            for line in self.autoconf:
                self.bh.exec0("echo", line, op, cfgp / "auto.conf")
                op = linux.Raw(">>")

    def kas_checkout(self) -> None:
        """
        call "kas checkout" so kas checksout all the needed sources
        for your ow build, and setup conf directory.
        """
        post = []
        if self.kaslayername is not None:
            post = [linux.Raw(f" {self.kaslayername}")]

        self.bh.exec0("mkdir", "-p", self.kasconfigpath)
        self.bh.exec0("cd", self.kasconfigpath)
        self.bh.exec0(
            "git",
            "-C",
            f"{self.kaslayername}",
            "pull",
            linux.Raw("||"),
            "git",
            "clone",
            self.kaslayer,
            "-b",
            self.kaslayerbranch,
            *post,
        )
        pre = []
        try:
            kas_ref_dir = self.bh.kas_ref_dir
            pre = [linux.Raw(f'KAS_REPO_REF_DIR="{kas_ref_dir._local_str()}"')]
        except:  # noqa: E722
            pass

        if self.netrc_file:
            pre.append(f"NETRC_FILE={self.netrc_file}")

        self.bh.exec0("cd", self.kas_get_basepath())
        # do not execute in case we use docker
        if self.container is False:
            self.bh.exec0(
                *pre, self.kascmd, "checkout", self.kasconfigpath / self.kasconfigfile
            )

        self.kas_create_autoconf()

    def kas_call_container(self, t: str) -> None:
        pre = []
        post = []
        try:
            kas_ref_dir = self.bh.kas_ref_dir
            pre.append(linux.Raw(f'KAS_REPO_REF_DIR="{kas_ref_dir._local_str()}"'))
        except:  # noqa: E722
            pass

        kasarg = []
        if self.git_credential_store:
            kasarg.append("--git-credential-store")
            kasarg.append(self.git_credential_store)

        if self.kas_runtime_args:
            kasarg.append("--runtime-args")
            kasarg.append(linux.Raw(self.kas_runtime_args))

        if self.kas_ssh_dir:
            kasarg.append("--ssh-dir")
            kasarg.append(self.kas_ssh_dir)

        path = self.kas_get_basepath()
        self.bh.exec0("cd", path)
        self.bh.exec0("pwd")
        # setup task and target
        task = "build"
        if "bitbake" in t and "-c" not in t:
            cmds = t.split(" ")
            target = cmds[-1]
        elif "-c" in t:
            cmds = t.split(" ")
            target = cmds[-1]
            foundtask = False
            for c in cmds:
                if foundtask:
                    task = c
                    break
                if "-c" in c:
                    foundtask = True
            if foundtask is False:
                raise RuntimeError("no task found, please set it with -c option")
        else:
            target = t

        # set NETRC_FILE
        if self.netrc_file:
            pre.append(f"NETRC_FILE={self.netrc_file}")

        # set KAS_TARGET
        pre.append(linux.Raw(f"KAS_TARGET='{target}'"))
        # set KAS_TASK
        pre.append(f"KAS_TASK={task}")
        if self.bitbakeoptions:
            bitopt = " ".join(self.bitbakeoptions)
            post.append(linux.Raw(f"-- {bitopt}"))

        self.bh.exec0(
            *pre,
            self.kascmd,
            *kasarg,
            "build",
            self.kasconfigpath / self.kasconfigfile,
            *post,
        )

        if self.container_engine:
            kasarg.append("KAS_CONTAINER_ENGINE={self.container_engine}")

    def kas_call_bitbake(self, t: str) -> None:
        if "bitbake" in t:
            # TODO make this better
            cmd = []
            cmd.append(linux.Raw(t))
        else:
            cmd = ["bitbake"]
            if " " in t:
                # TODO make this better
                cmd.append(linux.Raw(t))
            else:
                cmd.append(t)

        for opt in self.bitbakeoptions:
            cmd.append(opt)

        self.bh.exec0(*cmd)

    def kas_build(
        self,
        buildtargets=None,
    ) -> None:
        """
        build all `buildtargets`_.
        """
        if buildtargets is None:
            try:
                buildtargets = self.buildtargets
            except:  # noqa: E722
                raise RuntimeError("please specify buildtargets (array of strings)")

        self.kas_env_init()
        for t in buildtargets:
            if self.container:
                self.kas_call_container(t)
            else:
                self.kas_call_bitbake(t)

    def kas_shell(
        self,
    ) -> None:
        """
        enter kas shell
        """
        self.kas_checkout()
        pre = []
        post = []
        try:
            kas_ref_dir = self.bh.kas_ref_dir
            pre.append(f'KAS_REPO_REF_DIR="{kas_ref_dir._local_str()}"')
        except:  # noqa: E722
            pass

        if self.netrc_file:
            pre.append(f"NETRC_FILE={self.netrc_file}")

        kasarg = []
        if self.git_credential_store:
            kasarg.append("--git-credential-store")
            kasarg.append(self.git_credential_store)

        if self.kas_runtime_args:
            kasarg.append("--runtime-args")
            kasarg.append(str(self.kas_runtime_args))

        if self.kas_ssh_dir:
            kasarg.append("--ssh-dir")
            kasarg.append(self.kas_ssh_dir)

        path = self.kas_get_basepath()
        self.bh.exec0("cd", path)
        self.bh.exec0("pwd")

        if self.bitbakeoptions:
            bitopt = " ".join(self.bitbakeoptions)
            post.append(linux.Raw(f"-- {bitopt}"))

        cmd = ""
        if pre:
            cmd += " ".join(pre)

        # we always use the container command here, nevertheless what is setup
        cmd += f" {self.kaspath._local_str()}/kas/kas-container "
        if kasarg:
            cmd += " ".join(kasarg)

        cmd += f" shell {self.kasconfigpath._local_str()}/{self.kasconfigfile}"
        with tbot.log_event.command("kas-shell", cmd) as ev:
            with self.bh.ch.with_prompt("build$ "):
                self.bh.ch.sendline(cmd, read_back=True)
                with self.bh.ch.with_stream(ev, show_prompt=False):
                    self.bh.ch.read_until_prompt()
                    self.bh.ch.sendline(" ")
                    tbot.log.message(
                        f"Entering interactive kas shell ({tbot.log.c('CTRL+D to exit').bold}) ..."
                    )
                    self.bh.ch.attach_interactive(ctrld_exit=True)

    def kas_copy(
        self,
        resultimages=None,
    ) -> linux.path:
        """
        copy all results to tftp path on lab host

        resultimages is a list of image names, which should be created
        from the oe build.
        """
        if resultimages is None:
            try:
                resultimages = self.resultimages
            except:  # noqa: E722
                raise RuntimeError("please specify buildtargets (array of strings)")

        for r in resultimages:
            bhbasepath = self.kas_get_deploypath()
            bhf = bhbasepath / r
            labbasepath = self.lab.yocto_result_dir()
            shell_copy(bhf, labbasepath, remote_copy=True)

        return labbasepath
