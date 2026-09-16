import time

import tbot
import tbot.log_event as _log_event
from tbot import log
from tbot.log import c


def _install_command_timestamp() -> None:
    """
    Patch tbot.log_event.command() to prefix the command log with a
    "H:M:S" timestamp, e.g. "[foobar-uboot 06:15:57] run bootcmd"
    instead of just "[foobar-uboot] run bootcmd".

    Only active when the tbot flag "cmdtimestamp" is set (-f
    cmdtimestamp), so the default log format is unchanged otherwise.

    All call sites in tbot core do tbot.log_event.command(...), a
    dynamic attribute lookup on the module, so replacing the attribute
    here affects every one of them without touching tbot itself.
    """
    if "cmdtimestamp" not in tbot.flags:
        return

    control_mapping = _log_event._CONTROL_MAPPING

    def command(mach: str, cmd: str) -> log.EventIO:
        if log.IS_UNICODE:
            cmd = cmd.translate(control_mapping)

        timestamp = time.strftime("%H:%M:%S")

        ev = log.EventIO(
            ["cmd", mach],
            "[" + c(mach).yellow + " " + c(timestamp).dark + "] " + c(cmd).dark,
            verbosity=log.Verbosity.COMMAND,
            cmd=cmd,
        )

        if log.INTERACTIVE:
            if input(ev._prefix() + c("  OK [Y/n]? ").magenta).upper() not in (
                "",
                "Y",
            ):
                raise RuntimeError("Aborted by user")

        ev.prefix = "   ## "
        ev.verbosity = log.Verbosity.STDOUT
        return ev

    _log_event.command = command


_install_command_timestamp()
