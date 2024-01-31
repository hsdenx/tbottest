import tbot
import time
from tbot.machine import linux

from tbottest.common.utils import string_to_dict


def ps_parse_ps(
    log
) -> None:  # noqa: D107
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
            res = string_to_dict(line, '{PID}\s+{TID}\s+{CPU}\s+{NI}\s+{PRI}\s+{CMD}')
            result.append(res)
        except:
            continue
    
    return result

def lnx_measure_process(
    lnx: linux.LinuxShell,
    pname: str,
    intervall: float,
    loops: int,
) -> None:  # noqa: D107
    """
    measure for a process with name pname the cpu usage
    with intervall and loops. 

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
    while (i < int(loops)):
        try:
            log = lnx.exec0("ps", "-o", "pid,tid,pcpu,nice,priority,comm", "H", "-C", pname)
        except:
            log = ""

        resultnew = ps_parse_ps(log)
        new = {"loop":i, "values":resultnew}
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
                c.update({"val":cpuval})
            else:
                newcpu = {"name":val["CMD"], "val":float(val["CPU"])}
                cpu.append(newcpu)

        newentry = {"loop":loopval,"cpuvalues":cpu}
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
            if found == False:
                line +=  "0.0 "

        fd.write(line + "\n")

    fd.close()
    tbot.log.c(
        f"gnuplot dat file created in {fname}"
    ).yellow

    # create png image
    local.exec0(f"gnuplot", "-e", f"datafile='{fname}'", "-e", f"outputfile='{outputfilename}'", f"{gnuplotpath}/gnuplot-bar.gp")
    tbot.log.c(
        f"gnuplot created png file {outputfilename} on local host"
    ).yellow
    tbot.log.c(
        f"type there\n gwenview {outputfilename}\nto show the image"
    ).yellow
