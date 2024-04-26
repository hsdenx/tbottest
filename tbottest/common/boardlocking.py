import tbot
from tbot.context import Optional
from tbot.machine import linux
import tbottest.initconfig as ini


def lab_get_lockname(lab) -> linux.path.Path:
    """
    returns the lockfile name for the boardname on the lab lab
    """
    boardname = ini.generic_get_boardname()
    lockname = lab.tmpdir() / f"{boardname}-lablock"
    return lockname


@tbot.testcase
def lab_get_lock_info(
    lab: Optional[linux.LinuxShell] = None,
) -> str:
    """
    check if the locking file for the boardname exists.

    If not it returns 1, ""

    If lockingfile for the board exists return

    0, lockid

    The lockid is a string, which is in the first line of the lockfile
    """
    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)

        lockfile = lab_get_lockname(lab)
        if lockfile.is_file():
            lockid = lab.exec0("cat", lockfile)
            return 0, lockid.strip()
        else:
            return 1, ""


@tbot.testcase
def lab_get_lock(
    lab: Optional[linux.LinuxShell] = None,
) -> str:
    """
    Tries to get the lock for the boardname in the lab

    Therefore you must pass your locking ID (simple string
    with the tbot flag "lablockid:<your locking ID> when
    you start tbot.

    If there is no lockfile for the boardname in the lab,
    you get the lock for the boardname, until you call

    :py:func:`tbottest.common.boardlocking.lab_rm_lock`

    If there is a lockfile for the board already, you have
    to pass the correct locking ID, to get further. If you
    have not passed the correct locking ID, tbot will fail
    with an error!
    """
    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)

        lockfile = lab_get_lockname(lab)
        ret, activelockid = lab_get_lock_info(lab)
        lockid = None

        for f in tbot.flags:
            if "lablockid" in f:
                lockid = f.split(":")[1]

        if lockid is None:
            raise RuntimeError(
                "NO LABLOCKID passed, please pass tbot flag 'lablockid:<yourlockid>'"
            )

        if ret == 1:
            # no lockid active, set it
            lab.exec0("echo", lockid, linux.Raw(">"), lockfile)
            return 0, lockid
        else:
            # check lockid
            if lockid != activelockid:
                boardname = ini.generic_get_boardname()
                errstr = f"passed lockid {lockid} is not the same as lockid in file {lockfile._local_str()}. Boardname {boardname} is locked through ID {activelockid}"
                tbot.log.message(tbot.log.c(errstr).red)
                raise RuntimeError("errstr")


@tbot.testcase
def lab_rm_lock(
    lab: Optional[linux.LinuxShell] = None,
) -> str:
    """
    Tries to remove the lock for the boardname in the lab

    Therefore you must pass your locking ID (simple string
    with the tbot flag "lablockid:<your locking ID> when
    you start tbot.

    You must pass the correct lockid to remove the lock for
    the boardname in this lab.
    """
    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)

        lockfile = lab_get_lockname(lab)
        ret, activelockid = lab_get_lock_info(lab)
        lockid = None

        for f in tbot.flags:
            if "lablockid" in f:
                lockid = f.split(":")[1]

        if lockid is None:
            raise RuntimeError(
                "NO LABLOCKID passed, please pass tbot flag 'lablockid:<yourlockid>'"
            )

        if lockid != activelockid:
            boardname = ini.generic_get_boardname()
            errstr = f"passed lockid {lockid} is not the same as lockid in file {lockfile._local_str()}. Boardname {boardname} is locked through ID {activelockid}"
            tbot.log.message(tbot.log.c(errstr).red)
            raise RuntimeError("errstr")

        lab.exec0("rm", lockfile)
