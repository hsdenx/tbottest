"""
The Abatron BDI2000 as a tbot machine.

A telnet session to the BDI's command line, on which exec() runs one
command and returns what the BDI printed before its next prompt. The
machine for a board is set up from its [BDI2000_<boardname>] section in
tbot.ini, see GenericBDI2000 in labgeneric.py, and requested through the
role BDI2000:

.. code-block:: python

    with tbot.ctx.request(BDI2000) as bdi:
        bdi.exec("reset", "run")
"""
import contextlib
import re
import time
import typing

import tbot
from tbot.machine import shell

# The BDI's command line prompt, with the blank it may be followed by.
BDI2000_PROMPT = tbot.Re(r"BDI>[ ]?")

# "Target state      : debug mode" in the output of the BDI command info
TARGET_STATE = re.compile(r"Target state\s*:\s*(.*\S)")

# After "reset" the BDI prints "- TARGET: processing target init list ...."
# and its prompt, and only then "- TARGET: processing target init list
# passed" (or failed) once it has worked through the list.
INIT_LIST_STARTED = "processing target init list"
INIT_LIST_DONE = re.compile(r"init list (passed|failed)")

# "Config IP   : 192.168.3.1" and "Config File : amc/bdi/tqm855-AMC.cfg" in
# the output of the BDI command config without arguments
CONFIG_IP = re.compile(r"Config IP\s*:\s*(\S+)")
CONFIG_FILE = re.compile(r"Config File\s*:\s*(\S+)")

# config <file> <host> answers "Updating configuration passed. Booting ....."
# and the BDI boots with the new file at once, ending the telnet session
CONFIG_UPDATED = "Updating configuration passed"

# poweron_cmds entry that selects the BDI configuration file, see
# split_configname()
CONFIGNAME = "configname:"

# Messages with which the BDI reports a failed command. It has no return
# codes and goes on with the next command, so exec() looks for these in the
# output. load answers "# Cannot open file on host" when the file is missing
# on the TFTP server; without the check the following "go" starts whatever
# is in the target's memory.
BDI_ERRORS = [
    "Cannot open file on host",
]

# load reports success with this line; a load without it failed, whatever
# the BDI printed instead
LOAD_PASSED = "Loading program file passed"


def split_configname(
    cmds: typing.List[str],
) -> typing.Tuple[typing.Optional[str], typing.List[str]]:
    """
    Take the entry ``configname:<file>`` out of a list of BDI commands.

    It names the configuration file the BDI has to run with before the
    other commands are sent, see ensure_config().

    :returns: the file, or None without such an entry, and the other
        commands in their order
    :raises RuntimeError: if there is more than one such entry, or one
        without a file
    """
    names = [c[len(CONFIGNAME):].strip() for c in cmds if c.startswith(CONFIGNAME)]
    if len(names) > 1:
        raise RuntimeError(f"more than one {CONFIGNAME} entry in {cmds}")
    if names and not names[0]:
        raise RuntimeError(f"{CONFIGNAME} without a configuration file in {cmds}")
    rest = [c for c in cmds if not c.startswith(CONFIGNAME)]
    return (names[0] if names else None), rest


class BDI2000Shell(shell.Shell):
    """
    Shell for the command line of an Abatron BDI2000.
    """

    # seconds to wait for the end of the target init list
    init_list_timeout = 30.0

    @contextlib.contextmanager
    def _init_shell(self) -> typing.Iterator:
        with self.ch.with_prompt(BDI2000_PROMPT):
            self.ch.sendline("")
            self.ch.read_until_prompt(timeout=10)
            yield None

    def exec(self, *args: str) -> str:
        """
        Run one BDI command, the arguments joined by blanks.

        The BDI has no return codes, so check the returned output where it
        matters. The messages in BDI_ERRORS are checked here, and a load
        has to report LOAD_PASSED.

        :returns: what the BDI printed before its next prompt
        :raises RuntimeError: if the output contains one of BDI_ERRORS, or
            a load does not report LOAD_PASSED
        """
        cmd = " ".join(args)
        with tbot.log_event.command(self.name, cmd) as ev:
            self.ch.sendline(cmd)
            with self.ch.with_stream(ev, show_prompt=False):
                out = self.ch.read_until_prompt()
                out += self._wait_init_list(out)
            ev.data["stdout"] = out
        for err in BDI_ERRORS:
            if err in out:
                raise RuntimeError(f"BDI2000 command '{cmd}' failed: {err}")
        if cmd.split()[:1] == ["load"] and LOAD_PASSED not in out:
            raise RuntimeError(f"BDI2000 command '{cmd}' failed: {out.strip()}")
        return out

    def _wait_init_list(self, out: str) -> str:
        """
        If ``out`` shows the target init list started but not finished,
        wait for its end: the BDI prints its prompt before that, and a
        command sent in between is lost or answered out of order.

        :returns: what the BDI printed until the end of the init list
        :raises RuntimeError: if the BDI reports the init list failed
        """
        if INIT_LIST_STARTED not in out:
            return ""
        done = INIT_LIST_DONE.search(out)
        more = ""
        if done is None:
            res = self.ch.expect(
                ["init list passed", "init list failed"],
                timeout=self.init_list_timeout,
            )
            more = res.before + str(res.match) + res.after
            done = INIT_LIST_DONE.search(more)
            # drop what follows, then get a fresh prompt for the next command
            try:
                while True:
                    self.ch.read(timeout=0.5)
            except TimeoutError:
                pass
            self.ch.sendline("")
            self.ch.read_until_prompt(timeout=10)
        if done.group(1) == "failed":
            raise RuntimeError(f"BDI2000 target init list failed: {out}{more}")
        return more

    def target_state(self) -> str:
        """
        :returns: the target state the BDI command info reports, e.g.
            "debug mode", or "" if info does not report one
        """
        m = TARGET_STATE.search(self.exec("info"))
        return m.group(1) if m else ""

    def wait_target_state(
        self, state: str, timeout: float = 30.0, interval: float = 0.5
    ) -> None:
        """
        Ask the BDI with info until it reports the target state ``state``.

        After the board is powered on, the BDI first waits for the target
        Vcc and only then has the target in its startup state; a command
        like "reset run" sent before that is lost.

        :raises TimeoutError: if the state is not reached within
            ``timeout`` seconds
        """
        end = time.monotonic() + timeout
        while True:
            current = self.target_state()
            if current == state:
                return
            if time.monotonic() >= end:
                raise TimeoutError(
                    f"BDI2000 target state is {current!r}, not {state!r}, after {timeout} s"
                )
            time.sleep(interval)

    def config(self) -> typing.Tuple[str, str]:
        """
        :returns: the configuration file the BDI runs with and the host
            it loads it from, as the BDI command config reports them
        :raises RuntimeError: if config reports neither
        """
        out = self.exec("config")
        cfgfile = CONFIG_FILE.search(out)
        host = CONFIG_IP.search(out)
        if cfgfile is None or host is None:
            raise RuntimeError(f"BDI2000 config reports no Config File or Config IP: {out}")
        return cfgfile.group(1), host.group(1)

    def boot_config(self, cfgfile: str, timeout: float = 30.0) -> None:
        """
        Set the configuration file, loaded from the same host as the
        current one, with config <file> <host>.

        The BDI stores it, reports "Updating configuration passed.
        Booting ....." and boots with it right away, which ends the telnet
        session; this waits until the channel is closed. Request a new
        BDI2000 machine afterwards.

        :raises RuntimeError: if the BDI shows its prompt again instead of
            booting, or the channel closes without the update reported
        :raises TimeoutError: if the channel is still open after
            ``timeout`` seconds
        """
        _, host = self.config()
        cmd = f"config {cfgfile} {host}"
        out = b""
        with tbot.log_event.command(self.name, cmd) as ev:
            self.ch.sendline(cmd)
            end = time.monotonic() + timeout
            try:
                while time.monotonic() < end:
                    try:
                        out += self.ch.read(timeout=1.0)
                    except TimeoutError:
                        pass
                    if BDI2000_PROMPT.search(out):
                        ev.data["stdout"] = out.decode(errors="replace")
                        raise RuntimeError(
                            f"BDI2000 did not boot with {cfgfile}: {ev.data['stdout']}"
                        )
            except tbot.error.ChannelClosedError:
                ev.data["stdout"] = out.decode(errors="replace")
                if CONFIG_UPDATED not in ev.data["stdout"]:
                    raise RuntimeError(
                        f"BDI2000 closed the session without updating its "
                        f"configuration to {cfgfile}: {ev.data['stdout']}"
                    )
                return
        raise TimeoutError(
            f"BDI2000 telnet session still open {timeout} s after config {cfgfile}"
        )

    def interactive(self) -> None:
        """
        Connect tbot's terminal to the BDI's command line.
        """
        tbot.log.message("Entering BDI2000 command line ...")
        self.ch.attach_interactive()
        tbot.log.message("Exiting BDI2000 command line ...")


class BDI2000(BDI2000Shell, tbot.role.Role):
    """
    Role for the board's BDI2000.
    """

    pass


def ensure_config(
    request: typing.Callable[[], typing.ContextManager[BDI2000Shell]],
    cfgfile: str,
    timeout: float = 30.0,
    interval: float = 2.0,
) -> bool:
    """
    Make the BDI run with the configuration file ``cfgfile``.

    Ask the BDI which file it runs with; if it is another one, set
    ``cfgfile``, which makes the BDI boot with it, then connect again until
    it answers and check that it runs with ``cfgfile`` now.

    :param request: returns a context manager that yields a fresh BDI2000
        machine and tears it down on exit, e.g.
        ``lambda: tbot.ctx.request(BDI2000, exclusive=True)``
    :param timeout: seconds to wait for the BDI to boot and answer again
    :param interval: seconds between two connection attempts
    :returns: True if the BDI was restarted, False if it already ran with
        ``cfgfile``
    :raises TimeoutError: if the BDI does not answer within ``timeout``
        seconds after boot
    :raises RuntimeError: if the BDI runs with another file after boot
    """
    with request() as bdi:
        current, _ = bdi.config()
        if current == cfgfile:
            return False
        bdi.boot_config(cfgfile, timeout=timeout)

    end = time.monotonic() + timeout
    while True:
        try:
            with request() as bdi:
                current, _ = bdi.config()
            break
        except (RuntimeError, TimeoutError, tbot.error.ChannelClosedError) as e:
            # the BDI refuses or does not answer telnet while it restarts
            if time.monotonic() >= end:
                raise TimeoutError(
                    f"BDI2000 does not answer {timeout} s after boot: {e}"
                ) from e
            time.sleep(interval)

    if current != cfgfile:
        raise RuntimeError(f"BDI2000 runs with {current} after boot, not {cfgfile}")
    return True
