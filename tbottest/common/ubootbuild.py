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
    for building U-Boot. You can define a list of binaries,
    which are copied from binariesdir to U-Boots build dir
    before U-Boot gets builded (for example atf binary).

    The list of resulting binaries in resultbins you can
    copy to lab hosts tftp path with

    :py:func:`~UBBUILDMAN.bm_copy_results2lab`

    You may need to call also some make targets you can add
    through list of strings in makelist

    :param lab: lab host machine. must be valid
    :param bh: build host machine, must be valid
    :param defconfig: defconfig name of the board
    :param binarieslist: list of strings of binary names which get copied to builddir
    :param binariesdir: str of pathname where binaries are found
    :param resultbins: list of strings of resulting binarienames
    :param makelist: list of strings of make targets

    .. code-block:: python

        B = [
        {
            'defconfig': 'foo',
            'binaries': ['bl31.bin', 'mx8qx-mek-scfw-tcm.bin', 'mx8qxc0-ahab-container.img'],
            'binpath': 'tbottesting/tbotconfig/foo/binaries/',
            'resultbinaries': ['flash.bin'],
            'makelist': ['flash.bin'],
        },
        ]

        for b in B:
            bmcfg = UBBUILDMAN(lab, bh, b["defconfig"], b["binaries"], b["binpath"], b["resultbinaries"])
            bmcfg.bm_build_board()
            bmcfg.bm_copy_results2lab()

    """
    def __init__(
            self,
            lab:linux.LinuxShell,
            bh: linux.LinuxShell,
            defconfig: str = None,
            binarieslist: list = [],
            binariesdir: list = [],
            resultbins: list = [],
            makelist: list = []):
        if lab == None:
            raise RuntimeError("class UBBUILDMAN only with valid lab host possible")

        if bh == None:
            raise RuntimeError("class UBBUILDMAN only with valid build host possible")

        self.lab = lab
        self.bh = bh
        self.basedir = linux.Path(self.bh, self.bh.exec0("pwd").strip())
        # we call it from u-boot subdir tbottest, so U-Boot source base is one level back
        self.basedir = self.basedir / ".."

        self.defconfig = defconfig
        self.binarieslist = binarieslist
        self.binariesdir = self.basedir / binariesdir
        self.builddir = self.basedir / f"build-{self.defconfig}"
        self.builddirbuildman = self.builddir  / ".bm-work/00/build/"
        self.resultbins = resultbins
        self.makelist = makelist

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
        for f in self.binarieslist:
            self.bh.exec0("cp", self.binariesdir / f, self.builddirbuildman)

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
            ret, log = self.bh.exec(self.basedir / "tools/buildman/buildman",
                                    "-o", self.builddir, "-seP")

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


