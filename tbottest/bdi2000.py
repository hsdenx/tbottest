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


class BDI2000Shell(shell.Shell):
    """
    Shell for the command line of an Abatron BDI2000.
    """

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
            ev.data["stdout"] = out
        return out

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
