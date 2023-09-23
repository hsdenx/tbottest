#
# collection of linux testcases, for TPM
# may go into mainline
#
import typing
import tbot
from tbot.machine import linux
from tbot.context import Optional


@tbot.testcase
def board_lnx_tpm2(
    lab: typing.Optional[linux.LinuxShell] = None,
    lnx: Optional[linux.LinuxShell] = None,
) -> None:
    """
    simply check if we find some strings from tpm start
    check, if tpm has correct major version. And check
    if eltt2 tool detects correct vendor

    TODO: Make this testcase more generic.

    :param lab: lab linux machine
    :param lnx: board linux machine
    """
    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)

        if lnx is None:
            lnx = cx.request(tbot.role.BoardLinux)

        dmesgval = "2.0 TPM (device-id 0x1B, rev-id 22)"
        tpmnr = "0"
        tpmmajor = "2"
        tpmvendorstring = "SLB9670"
        tpmdev = f"/dev/tpm{tpmnr}"

        out = lnx.exec0("dmesg", linux.Pipe, "grep", "tpm")
        if dmesgval not in out:
            raise RuntimeError("tpm not found")

        # check if device exists
        lnx.exec0("ls", "-al", tpmdev)

        out = lnx.exec0("cat", f"/sys/class/tpm/tpm{tpmnr}/tpm_version_major")
        if tpmmajor not in out:
            raise RuntimeError("tpm major {tpmmajor} not found, found instead {out}")

        try:
            lnx.exec0("eltt2", "-h")
        except:  # noqa: E722
            # no eltt2 tool ... exit
            return

        out = lnx.exec0("eltt2", "-gvc")
        if tpmvendorstring not in out:
            raise RuntimeError(f"vendor {tpmvendorstring} not found")
