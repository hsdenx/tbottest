import os
import tbot
from tbot.context import Optional
from tbot.machine import linux
from tbot.machine import board
from tbot.machine import connector
from tbot.tc import shell

class UBBUILDMAN:
    """
    simple class for some useful buildman tool abstractions
    for building U-Boot. You can define a subdirname
    "binsubpath" which is a subdir on lab hosts tftp directory
    in which needed binaries for complete and working U-Boot
    build are found. tbot copies all files found in this subdirectory
    to U-Boots build directory on build host.

    Same for downsream patches. You can define a name for
    a subdirectory found on labhosts tftp directory for the
    board with name "ubootpatchsubpath". All patches found in
    this directory, are copied to U-Boot source directory
    on build host and applied to the current U-Boot source
    code.

    The list of resulting binaries in resultbins you can
    copy to lab hosts tftp path with

    :py:func:`~UBBUILDMAN.bm_copy_results2lab`

    You may need to call also some make targets you can add
    through list of strings in makelist

    :param lab: lab host machine. must be valid
    :param bh: build host machine, must be valid
    :param ubootpatchsubpath: str subdir on labhosts tftp directory with downstream U-Boot patches
    :param defconfig: defconfig name of the board
    :param binariessubpath: str subdir on labhosts tftp directory where needed binaries are found
    :param resultbins: list of strings of resulting binarienames
    :param makelist: list of strings of make targets

    .. code-block:: python

        B = [
        {
            'defconfig': 'foo',
            'ubootpatchsubpath': 'uboot-patches',
            'binsubpath': 'binaries',
            'resultbinaries': ['flash.bin'],
            'makelist': ['flash.bin'],
        },
        ]

        for b in B:
            bmcfg = UBBUILDMAN(lab, bh, b["ubootpatchsubpath"], b["binsubath"], b["defconfig"], b["resultbinaries"])
            bmcfg.bm_build_board()
            bmcfg.bm_copy_results2lab()

    """
    def __init__(
            self,
            lab:linux.LinuxShell,
            bh: linux.LinuxShell,
            ubootpatchsubpath: str = None,
            ubootbinariessubpath: str = None,
            defconfig: str = None,
            resultbins: list = [],
            makelist: list = []):
        if lab == None:
            raise RuntimeError("class UBBUILDMAN only with valid lab host possible")

        if bh == None:
            raise RuntimeError("class UBBUILDMAN only with valid build host possible")

        self.lab = lab
        self.bh = bh
        self.ubootpatchsubpath = ubootpatchsubpath
        self.ubootbinariessubpath = ubootbinariessubpath
        self.basedir = linux.Path(self.bh, self.bh.exec0("pwd").strip())
        # we call it from u-boot subdir tbottest, so U-Boot source base is one level back
        self.basedir = self.basedir / ".."

        self.tbotbranchname = "tbot-build"
        self.defconfig = defconfig
        self.ubootpatchpath = self.basedir / self.ubootpatchsubpath
        self.builddir = self.basedir / f"build-{self.defconfig}"
        self.builddirbuildman = self.builddir  / ".bm-work/00/build/"
        self.resultbins = resultbins
        self.makelist = makelist

    @tbot.testcase
    def bm_get_uboot_patches(
        self,
    ) -> None:  # noqa: D107
        """
        copy boardspecfic downstream patches found on lab
        host in current tftp path for the board in subdir
        "uboot-patches" to the build host
        """
        self.bh.exec0("rm", "-rf", self.ubootpatchpath)
        self.bh.exec0("mkdir", "-p", self.ubootpatchpath)
        pf = "0*"
        shell.copy(self.lab.tftp_dir() / f"uboot-patches/{pf}", self.ubootpatchpath, remote_copy=True)

    @tbot.testcase
    def bm_apply_uboot_patches(
        self,
    ) -> None:  # noqa: D107
        """
        apply the patches which are in self.ubootpatchpath
        """
        # check if we are on self.tbotbranchname
        # if so, do nothing
        # check if branchname exists
        ret, commitidtbotbranch = self.bh.exec("git", "rev-parse", "--verify", self.tbotbranchname)
        if ret == 0:
            # branch exists, check if we are currently on it
            # if so, do nothing
            ret, log = self.bh.exec("git", "rev-parse", "--verify", "HEAD")
            if commitidtbotbranch == log:
                tbot.log.message(tbot.log.c(f"{self.tbotbranchname} currently checked out").yellow)
                return


        self.bh.exec("git", "branch", "-D", self.tbotbranchname)
        self.bh.exec0("git", "checkout", "-b", self.tbotbranchname)
        self.bh.exec0("pwd")
        pp = f"{self.ubootpatchpath._local_str()}/*.patch"
        self.bh.exec0("git", "am", "-3", linux.Raw(pp))

    @tbot.testcase
    def bm_build_prepare(
        self,
    ) -> [str]:  # noqa: D107
        """
        setup all stuff we need for building U-Boot
        """
        self.bh.exec0("cd", self.basedir)
        self.bh.exec0("pip", "install", "-r",
                        self.basedir / "tools/buildman/requirements.txt")
        log = self.bh.exec0(self.basedir / "tools/buildman/buildman",
                            "--list-tool-chains")
        if "--fetch-arch all" in log:
            # no buildman setup at all, fetch all
            self.bh.exec0(self.basedir / "tools/buildman/buildman",
                            "--fetch-arch", "all")
            log = self.bh.exec0(self.basedir / "tools/buildman/buildman",
                            "--list-tool-chains")

        # detect toolchain path and gcc name
        arch = self.bh.exec0(self.basedir / "tools/buildman/buildman",
                            "--print-arch", "--boards", self.defconfig)
        arch = arch.strip()

        found = False
        for line in log.split("\n"):
            if arch in line:
                found = True

        if found == False:
            ret, log = self.bh.exec(self.basedir / "tools/buildman/buildman",
                                    "--fetch-arch", arch)
            log = self.bh.exec0(self.basedir / "tools/buildman/buildman",
                                "--list-tool-chains")

        found = False
        for line in log.split("\n"):
            if arch in line:
                found = True
                toolchain = line.split(":")[1]
                toolchain = toolchain.strip()

                gcc = os.path.basename(toolchain)
                toolchainpath = os.path.dirname(toolchain)

        if found == False:
            raise RuntimeError(f"Could not fetch toolchain for arch {arch}")

        self.bh.exec0("mkdir", "-p", self.builddirbuildman)
        ret, log = self.lab.exec("ls", "-1", self.lab.tftp_dir() / self.ubootbinariessubpath)
        log = log.strip("\n")
        for f in log.split("\n"):
            shell.copy(self.lab.tftp_dir() / self.ubootbinariessubpath / f, self.builddirbuildman, remote_copy=True)

        self.bm_get_uboot_patches()
        self.bm_apply_uboot_patches()

        return arch, gcc, toolchainpath

    @tbot.testcase
    def bm_build_board(
        self
    ) -> None:  # noqa: D107
        """
        setup all stuff we need for building U-Boot
        """
        arch, gcc, toolchainpath = self.bm_build_prepare()

        ret, log = self.bh.exec(self.basedir / "tools/buildman/buildman",
                                "-c", "1", "-o", self.builddir, "--boards",
                                self.defconfig)
        if ret != 0:
            ret2, log = self.bh.exec(self.basedir / "tools/buildman/buildman",
                                    "-o", self.builddir, "-seP")
            raise RuntimeError(f"Build {self.defconfig} failed with ret {ret}")

        # get shell variable values
        if self.makelist:
            if arch == "aarch64":
                self.bh.exec0("export", "ARCH=arm64")
            else:
                self.bh.exec0("export", f"ARCH={arch}")
            gcc = gcc.replace("gcc", "")
            self.bh.exec0("export", f"CROSS_COMPILE={gcc}")
            self.bh.exec0("export", linux.Raw(f"PATH=$PATH:{toolchainpath}"))

        # call make targets
        for t in self.makelist:
            self.bh.exec("make", "V=1", f"O={self.builddirbuildman._local_str()}", t)
            if ret != 0:
                raise RuntimeError(f"Build {self.defconfig} failed with ret {ret} for Makefile target {t}")

        for f in self.resultbins:
            self.bh.exec0("pwd")
            self.bh.exec0("ls", "-al", self.builddirbuildman / f)

    @tbot.testcase
    def bm_copy_results2lab(
        self
    ) -> None:  # noqa: D107
        """
        copy results to lab
        """
        for f in self.resultbins:
            shell.copy(self.builddirbuildman / f, self.lab.tftp_dir()/f"{f}-githubci", remote_copy=True)


