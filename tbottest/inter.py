import tbot

# only to have interactive commands handy and do not use the ones
# from tbot, see https://tbot.tools/quickstart.html#directory-structure


@tbot.testcase
def board() -> None:
    """Open an interactive session on the board's serial console."""
    with tbot.ctx.request(tbot.role.Board) as b:
        b.interactive()


@tbot.testcase
def linux() -> None:
    """Open an interactive session on the board's Linux shell."""
    with tbot.ctx.request(tbot.role.BoardLinux) as lnx:
        lnx.interactive()


@tbot.testcase
def local() -> None:
    """Open an interactive session on the board's Linux shell."""
    with tbot.ctx.request(tbot.role.LocalHost) as lnx:
        lnx.interactive()


@tbot.testcase
def uboot() -> None:
    """Open an interactive session on the board's U-Boot shell."""
    tbot.ctx.teardown_if_alive(tbot.role.BoardLinux)
    with tbot.ctx.request(tbot.role.BoardUBoot) as ub:
        ub.interactive()


@tbot.testcase
def lab() -> None:
    """Start an interactive shell on the lab-host."""
    with tbot.ctx.request(tbot.role.LabHost) as lh:
        lh.interactive()


@tbot.testcase
def build() -> None:
    """Start an interactive shell on the build-host."""
    with tbot.ctx.request(tbot.role.BuildHost) as bh:
        bh.exec0("cd", bh.workdir)
        bh.interactive()
