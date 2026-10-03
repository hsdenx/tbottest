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
        matters.

        :returns: what the BDI printed before its next prompt
        """
        cmd = " ".join(args)
        with tbot.log_event.command(self.name, cmd) as ev:
            self.ch.sendline(cmd)
            with self.ch.with_stream(ev, show_prompt=False):
                out = self.ch.read_until_prompt()
                out += self._wait_init_list(out)
            ev.data["stdout"] = out
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
