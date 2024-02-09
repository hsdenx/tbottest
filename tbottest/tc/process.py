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


def ps_parse_top(log) -> None:  # noqa: D107
    """
    parse the log output from top command
    called with the options

    top -b -n X -d X -c -H | awk '($1=="%Cpu(s):")||($8=="R")||($1=="MiB") {print}'

    .. bash:

        %Cpu(s): 92.9 us,  6.2 sy,  0.0 ni,  0.9 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st
        MiB Mem :    491.0 total,    164.2 free,    143.9 used,    182.9 buff/cache
        MiB Swap:      0.0 total,      0.0 free,      0.0 used.    321.8 avail Mem
          267 weston    20   0  243672  85304  13792 R  93.8  17.0  32:32.89 /usr/bin/weston --modules=systemd-notify.so
         2119 root      20   0    4128   1944   1496 R   5.4   0.4   0:00.26 top -b -n 3 -d 1 -c -H

    .. warning::

        This works not with the busybox version

    You get back an arrray containing dictionary

    .. code-block:: python

        {"loop":<loop>, "cpu_system":<cpu dictionary>, "values",<array of values>}

    cpu dictionary contains a dictionary of the form:

    .. code-block:: python

        {'USER': '93.8', 'SYSTEM': '4.4', 'NICE': '0.0', 'IDLE': '1.8', 'WA': '0.0', 'HI': '0.0', 'SI': '0.0', 'ST': '0.0'}

    array of values contain dictionaries of the form:

    .. code-block:: python

        {'PID': '267', 'USER': 'weston', 'PR': '20', 'NI': '0', 'VIRT': '243672', 'RES': '85304', 'SHR': '13792', 'S': 'R', 'CPU': '62.5', 'MEM': '17.0', 'TIME': '93:29.61', 'CMD': '/usr/bin/weston'}

    """
    result = []
    if len(log) == 0:
        return result

    i = 0
    loopresult = []
    cpu = {}
    for line in log.split("\n"):
        try:
            if "Cpu(s)" in line:
                if len(loopresult):
                    new = {"loop": i, "cpu_system": cpu, "values": loopresult}
                    result.append(new)
                i += 1
                loopresult = []
                # example top output
                # %Cpu(s): 74.4 us, 20.5 sy,  0.0 ni,  0.0 id,  0.0 wa,  0.0 hi,  5.1 si,  0.0 st
                cpu = string_to_dict(
                    line,
                    "%Cpu\(s\):\s+{USER}\s+us,\s+{SYSTEM}\s+sy,\s+{NICE}\s+ni,\s+{IDLE}\s+id,\s+{WA}\s+wa,\s+{HI}\s+hi,\s+{SI}\s+si,\s+{ST}\s+st",  # noqa: W605
                )  # noqa: W605
                continue
            if "MiB Mem" in line:
                # ignore
                # print("Found MiB mem")
                continue
            if "MiB Swap" in line:
                # ignore
                # print("Found MiB Swap")
                continue

            #   PID USER      PR  NI    VIRT    RES    SHR S  %CPU  %MEM     TIME+ COMMAND
            res = string_to_dict(
                line,
                "{PID}\s+{USER}\s+{PR}\s+{NI}\s+{VIRT}\s+{RES}\s+{SHR}\s+{S}\s+{CPU}\s+{MEM}\s+{TIME}\s+{CMD}",  # noqa: W605
            )  # noqa: W605
            loopresult.append(res)
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
        res = []
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

    Array of values contains a dictionary with, see

    :py:func:`tbottest.tc.process.ps_parse_ps`

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
                # log = lnx.exec0("ps", "a", "-o", "pid,tid,pcpu,nice,priority,comm", "H")
                log = lnx.exec0("ps", "a", "-o", "pid,tid,pcpu,nice,priority,comm")
        except:
            log = ""

        resultnew = ps_parse_ps(log)
        new = {"loop": i, "values": resultnew}
        result.append(new)

        time.sleep(intervall)
        i += 1

    return result


def lnx_measure_top(
    lnx: linux.LinuxShell,
    intervall: float,
    loops: int,
) -> None:  # noqa: D107
    """
    call top with intervall ```intervall`` and ```loops``` and
    analyse it

    .. warning::

        This works not with the busybox version

    you get back an array which contains a dictionary described
    in testcase

    :py:func:`tbottest.tc.process.ps_parse_top`
    """
    log = lnx.exec0(
        linux.Raw(
            f'top -b -n {loops} -d {intervall} -c -H | awk \'($1=="%Cpu(s):")||($8=="R")||($1=="MiB") {{print}}\''
        )
    )
    return ps_parse_top(log)


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
            ps_create_measurement_png(local, pname, intervall, loops, result)

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


def top_create_measurement_png(
    local: linux.LinuxShell,
    intervall,
    loops,
    result,
) -> None:  # noqa: D107
    """
    create a png on local host based on the results result
    from testcase:

    :py:func:`tbottest.tc.process.lnx_measure_top`

    store the gnuplot data in

    .. code-block:: bash

        results/measurements/process/{loops}_{intervall}_top.dat

    call gnuplot with the config file

    .. code-block:: bash

        results/measurements/process/gnuplot-bar-cpustat.gp

    The output png is stored in ```process-usage.png```. Example for
    viewing it:

    .. code-block:: bash

        $ gwenview process-usage.png

    example usage of this testcase:

    .. code-block:: python

        loops = 30
        intervall = 1.0

        with tbot.ctx() as cx:
            if lab is None:
                lab = cx.request(tbot.role.LabHost)

            if lnx is None:
                lnx = cx.request(tbot.role.BoardLinux)

            result = lnx_measure_top(lnx, intervall, loops)

            local = cx.request(tbot.role.LocalHost)
            top_create_measurement_png(local, intervall, loops, result)

    example png:

    .. image:: ../results/measurements/process/process-usage.png

    """
    cpuvalues = []
    pnamelist = []
    for loop in result:
        loopval = loop["loop"]
        cpusysval = loop["cpu_system"]

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

        # add cpu and system time
        cputime = float(cpusysval["USER"]) + float(cpusysval["SYSTEM"])
        newcpu = {"name": "cpu_user", "val": cpusysval["USER"]}
        cpu.append(newcpu)
        newcpu = {"name": "cpu_system", "val": cpusysval["SYSTEM"]}
        cpu.append(newcpu)
        newcpu = {"name": "cpu_complete", "val": cputime}
        cpu.append(newcpu)

        newentry = {"loop": loopval, "cpuvalues": cpu}
        cpuvalues.append(newentry)

    pnamelist.append("cpu_user")
    pnamelist.append("cpu_system")
    pnamelist.append("cpu_complete")

    gnuplotpath = "results/measurements/process"
    filename = f"{loops}_{intervall}_top.dat"
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
        f"{gnuplotpath}/gnuplot-bar-cpustat.gp",
    )
    tbot.log.c(f"gnuplot created png file {outputfilename} on local host").yellow
    tbot.log.c(f"type there\n gwenview {outputfilename}\nto show the image").yellow
