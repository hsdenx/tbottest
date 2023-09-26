import time

from tbot import log

__all__ = ("doc_begin", "doc_image", "doc_cmd", "doc_tag", "doc_end")

"""
    Documentation generator searchs for a "doc" "begin" event
    and searches for a file with name docid_begin.rst and writes
    the content to the output file. After start is found it then
    writes all log types "cmd" to output, until it finds an "end".
    Nested "begin" is possible.

    log types                                           output

    types != "doc"                                      none

    "doc", "begin", "docid" -> ? docid_begin.rst ->     content of docid_begin.rst
    "cmd"                                               "data" in cmd block"
    "cmd"                                               "data" in cmd block", added to the above
                                                        cmd block
    "doc", "begin", "docid" -> ? docid_begin.rst ->     content of docid_begin.rst
    "cmd"                                               "data" in cmd block
    "doc", "end", "docid" -> ? docid_end.rst ->         content of docid_end.rst
    "cmd"                                               "data" in cmd block
    "doc", "end", "docid" -> ? docid_end.rst ->         content of docid_end.rst

    "doc", "cmd", "docid" -> ? docid_cmd.rst ->         content of docid_cmd.rst

    types != "doc"                                      none


    "doc", "tag", "tagid" "tagval"                      replace in the resulting rst
                                                        file all "tagid" occurencies
                                                        with "tagval".
                                                        If tagid contains "fixlen",
                                                        to short "tagval" are filled up with
                                                        spaces.

    :param str docid: ID of the doc section
"""


def doc_begin(docid: str) -> None:
    """
    Log a doc ID beginning.

    :param str docid: ID of the doc section
    """
    log.EventIO(
        ["doc", "begin"],
        message=f"add doc begin {docid}",
        verbosity=log.Verbosity.CHANNEL,
        docid=docid,
    )


def doc_image(imagename: str) -> None:
    """
    insert image imagename into rst

    :param str imagename: name of the image which gets inserted into rst
    """
    log.EventIO(
        ["doc", "image"],
        message=f"add doc image {imagename}",
        verbosity=log.Verbosity.CHANNEL,
        imagename=imagename,
    )


def doc_cmd(docid: str) -> None:
    """
    Log a doc cmd ID event

    :param str docid: ID of the doc cmd
    """
    log.EventIO(
        ["doc", "cmd"],
        message=f"add doc cmd {docid}",
        verbosity=log.Verbosity.CHANNEL,
        docid=docid,
    )


def doc_tag(tagid: str, tagval: str) -> None:
    """
    Log a doc tag ID event

    :param str docid: ID of the doc tag
    """
    log.EventIO(
        ["doc", "tag"],
        message=f"add doc tag {tagid} {tagval}",
        verbosity=log.Verbosity.CHANNEL,
        tagid=tagid,
        tagval=tagval,
    )


def doc_end(docid: str) -> None:
    """
    Log a doc ID end.

    :param str docid: ID of the doc section
    """
    log.EventIO(
        ["doc", "end"],
        message=f"add doc end {docid}",
        verbosity=log.Verbosity.CHANNEL,
        docid=docid,
    )


def tbot_start() -> None:
    print(log.c("tbot").yellow.bold + " starting ...")
    log.NESTING += 1


def tbot_end(success: bool) -> None:
    log.message(
        log.c(
            log.u(
                "────────────────────────────────────────",
                "----------------------------------------",
            )
        ).dark
    )

    if log.LOGFILE is not None:
        log.message(f"Log written to {log.LOGFILE.name!r}")

    msg = log.c("SUCCESS").green.bold if success else log.c("FAILURE").red.bold
    duration = time.monotonic() - log.START_TIME
    log.EventIO(
        ["tbot", "end"],
        msg + f" ({duration:.3f}s)",
        nest_first=log.u("└─", "\\-"),
        verbosity=log.Verbosity.QUIET,
        success=success,
        duration=duration,
    )
