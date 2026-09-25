"""
Interactive access to an Abatron BDI2000 debugger over telnet.

The debugger is set up per board in tbot.ini::

    [BDI2000_<boardname>]
    ip = 192.168.3.101

and reached with telnet from the lab host.
"""
import tbot


@tbot.testcase
def bdi2000() -> None:
    """
    Open an interactive telnet session to the board's BDI2000.

    Leave it like any other interactive session, with CTRL+] three times
    within one second. The session also ends when telnet exits by itself.
    """
    with tbot.ctx.request(tbot.role.LabHost) as lh:
        ip = lh.get_bdi2000_ip()

        # As in tbot's Bash.interactive(): an outer shell whose prompt ends
        # the interactive session once telnet has exited. The prompt is
        # assigned in two quoted halves, so the echo of the assignment does
        # not contain it and cannot be taken for the prompt.
        head = "BDI2000-END-"
        tail = hex(0x5F3A1C9E7D2B4086)[2:]
        endstr = head + tail
        lh.ch.sendline("bash --norc --noprofile")
        lh.ch.sendline(f"PS1='{head}''{tail}'")
        lh.ch.read_until_prompt(prompt=endstr)

        # CTRL+] is telnet's escape character by default, so telnet would
        # catch the first of tbot's three. Move telnet's escape to CTRL+^
        # (0x1e), which is not typed by accident, and use it below.
        lh.ch.sendline("telnet -e $'\\x1e' " + lh.escape(ip))
        tbot.log.message(f"Entering telnet session to BDI2000 at {ip} ...")
        lh.ch.attach_interactive(end_magic=endstr)
        tbot.log.message("Exiting telnet session ...")

        # After tbot's escape telnet is still running: leave it through its
        # escape character, then leave the outer shell.
        lh.ch.send("\x1e")
        lh.ch.sendline("quit")
        try:
            lh.ch.read_until_prompt(prompt=endstr, timeout=2)
        except TimeoutError:
            pass
        lh.ch.sendline("exit")
        lh.ch.read_until_prompt()
