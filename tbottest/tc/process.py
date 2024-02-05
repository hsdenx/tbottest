import tbot
import time
from tbot.machine import linux

from tbottest.common.utils import string_to_dict


def ps_parse_ps(log) -> None:  # noqa: D107
    """
    parse the log output from ps command
    called with the options

    ```pid,tid,pcpu,nice,priority,comm", "H", "-C", pname```

    .. warning::

        This works not with the busybox version

    """
    result = []
    if len(log) == 0:
        return result

    first = True
    for line in log.split("\n"):
        if first:
            first = False
            continue

        try:
            res = string_to_dict(
                line, "{PID}\s+{TID}\s+{CPU}\s+{NI}\s+{PRI}\s+{CMD}"  # noqa: W605
            )  # noqa: W605
            result.append(res)
        except:
            continue

    return result


def lnx_get_process_cpu_usage(
    lab: linux.LinuxShell,
    lnx: linux.LinuxShell,
    pname: str,
) -> None:  # noqa: D107
    """
    get the current cpu usage of process with name ```pname```

    you get back a dict of the following format:

    .. code-block:: python

        {'PID': '172', 'USER': 'root', 'PR': '20', 'NI': '0', 'VIRT': '14720', 'RES': '4340', 'SHR': '3748', 'S': 'S', 'CPU': '0.0', 'MEM': '0.9', 'TIME': '3:31.29', 'CMD': 'rngd'}
    """
    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)
        if lnx is None:
            lnx = cx.request(tbot.role.BoardLinux)

        try:
            log = lnx.exec0(linux.Raw(f"top -b -d 1 -n 1 | grep {pname}"))
            # output of top command is
            # PID USER      PR  NI    VIRT    RES    SHR S  %CPU  %MEM     TIME+ COMMAND
            # 172 root      20   0   14588   2344   1912 S  62.5   0.5   0:37.31 rngd
            res = string_to_dict(
                log,
                "{PID}\s+{USER}\s+{PR}\s+{NI}\s+{VIRT}\s+{RES}\s+{SHR}\s+{S}\s+{CPU}\s+{MEM}\s+{TIME}\s+{CMD}",  # noqa: W605
            )
        except:
            res = {}

        return res


def lnx_get_cpu_stats(
    lnx: linux.LinuxShell,
) -> None:  # noqa: D107
    """
    get cpu stats from top command

    you get back a dict of the following format:

    .. code-block:: python

        {'CPU': '0.0', 'SYS': '20.0', 'NI': '0.0', 'IDLE': '75.0', 'WA': '0.0', 'HI': '0.0', 'SI': '5.0', 'ST': '0.0'}
    """
    with tbot.ctx() as cx:
        if lnx is None:
            lnx = cx.request(tbot.role.BoardLinux)

        # call top twice, as first has big cpu time from top itself
        log = lnx.exec0(linux.Raw('top -b -d 0.5 -n 2 | grep "%Cpu(s)"'))
        # output of top command is
        # %Cpu(s): 82.1 us, 17.9 sy,  0.0 ni,  0.0 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st
        i = 1
        for line in log.split("\n"):
            # ignore first line
            if i:
                i = 0
                continue

            if "Cpu" not in line:
                continue

            res = string_to_dict(
                line,
                "\%Cpu\(s\)\:\s+{CPU} us,\s+{SYS} sy,\s+{NI} ni,\s+{IDLE} id,\s+{WA} wa,\s+{HI} hi,\s+{SI} si,\s+{ST} st",  # noqa: W605
            )

        return res


def lnx_measure_process(
    lnx: linux.LinuxShell,
    pname: str,
    intervall: float,
    loops: int,
) -> None:  # noqa: D107
    """
    measure for a process with name ```pname``` the cpu usage
    with ```intervall``` and ```loops```. If ```pname``` is
    empty, measure all processes.

    .. warning::

        This works not with the busybox version

    you get back an array which contains a dictionary with
    entry

    .. code-block:: python

        {"loop":<loop>, "values",<array of values>}

    Array of values contains a dictionary with

    .. code-block:: python

        {'PID': <PID>, 'TID': <TID>, 'CPU': <cpu usage>, 'NI': <nice value>, 'PRI': <priority of TID<, 'CMD': <command>}

    If there is no such process ```values``` entry is empty
    """
    i = 0
    result = []
    while i < int(loops):
        try:
            if len(pname):
                log = lnx.exec0(
                    "ps", "-o", "pid,tid,pcpu,nice,priority,comm", "H", "-C", pname
                )
            else:
                log = lnx.exec0("ps", "-o", "pid,tid,pcpu,nice,priority,comm", "H")
        except:
            log = ""

        resultnew = ps_parse_ps(log)
        new = {"loop": i, "values": resultnew}
        result.append(new)

        time.sleep(intervall)
        i += 1

    return result


def ps_create_measurement_png(
    local: linux.LinuxShell,
    pname,
    intervall,
    loops,
    result,
) -> None:  # noqa: D107
    """
    create a png on local host based on the results result
    from testcase:

    :py:func:`tbottest.tc.process.lnx_measure_process`

    store the gnuplot data in

    .. code-block:: bash

        results/measurements/process/{loops}_{intervall}_{pname}.dat

    call gnuplot with the config file

    .. code-block:: bash

        results/measurements/process/gnuplot-bar.gp

    The output png is stored in ```process-usage.png```. Example for
    viewing it:

    .. code-block:: bash

        $ gwenview process-usage.png

    example usage of this testcase:

    .. code-block:: python

        loops = 30
        intervall = 1.0
        pname = "QtWebEngineProc"

        with tbot.ctx() as cx:
            if lab is None:
                lab = cx.request(tbot.role.LabHost)

            if lnx is None:
                lnx = cx.request(tbot.role.BoardLinux)

            result = lnx_measure_process(lnx, pname, intervall, loops)

            local = cx.request(tbot.role.LocalHost)
            top_create_measurement_png(local, pname, intervall, loops, result)

    """
    cpuvalues = []
    pnamelist = []
    for loop in result:
        loopval = loop["loop"]

        # values maybe empty, happens if ps command does not find the process!
        values = loop["values"]

        # count same val["CMD"] into one value
        cpu = []
        for val in values:
            if not val["CMD"] in pnamelist:
                pnamelist.append(val["CMD"])

            curdict = {}
            for c in cpu:
                if c["name"] == val["CMD"]:
                    curdict = c
                    break

            if len(curdict):
                cpuval = c["val"]
                cpuval += float(val["CPU"])
                c.update({"val": cpuval})
            else:
                newcpu = {"name": val["CMD"], "val": float(val["CPU"])}
                cpu.append(newcpu)

        newentry = {"loop": loopval, "cpuvalues": cpu}
        cpuvalues.append(newentry)

    gnuplotpath = "results/measurements/process"
    filename = f"{loops}_{intervall}_{pname}.dat"
    fname = gnuplotpath + "/" + filename
    outputfilename = "process-usage.png"
    try:
        fd = open(fname, "w")
    except:
        tbot.log.message(
            tbot.log.c(
                f"could not open {fname}, May you create {gnuplotpath}, if you want to use the results later"
            ).yellow
        )
        return

    headline = "loop "
    for pname in pnamelist:
        headline += pname + " "

    fd.write(headline + "\n")

    i = 0
    for cpuv in cpuvalues:
        i += 1
        cpu = cpuv["cpuvalues"]
        line = f"{i} "
        for pname in pnamelist:
            found = False
            for c in cpuv["cpuvalues"]:
                if pname == c["name"]:
                    found = True
                    line += str(c["val"]) + " "
            if not found:
                line += "0.0 "

        fd.write(line + "\n")

    fd.close()
    tbot.log.c(f"gnuplot dat file created in {fname}").yellow

    # create png image
    cmcount = len(pnamelist) + 1
    local.exec0(
        "gnuplot",
        "-e",
        f"datafile='{fname}'",
        "-e",
        f"outputfile='{outputfilename}'",
        "-e",
        f"columcount='{cmcount}'",
        f"{gnuplotpath}/gnuplot-bar.gp",
    )
    tbot.log.c(f"gnuplot created png file {outputfilename} on local host").yellow
    tbot.log.c(f"type there\n gwenview {outputfilename}\nto show the image").yellow
