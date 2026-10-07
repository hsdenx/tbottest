.. py:module:: tbottest.generic

``tbottest.generic``
=========================

This is an example approach for a hopefully easy to use lab and board support.

Therefore we use ini file based configuration, based on

https://docs.python.org/3/library/configparser.html

with all its limitiations.

But it showed, that for a first use of tbot, it is easier to explain
to edit a tbot.ini file and start!

.. _requirementslabhost:

requirements for lab host
-------------------------

sudo command should work without entering a password (or add support for this
in tbot!)

You should be able to ssh between lab host, build host and board
without entering a password or something else!

supported hardware/tools
------------------------

Console access to the board with:

* picocom, see `[PICOCOM_BOARDNAME]`_
* kermit, see `[KERMIT_BOARDNAME]`_
* telnet, see `[TELNET_BOARDNAME]`_
* a script of your own, see `[SCRIPTCOM_BOARDNAME]`_
* ssh into the running Linux of the board, flag ssh

Power control with:

* sispmctl, see `[SISPMCTRL_BOARDNAME]`_
* Tinkerforge, see `[TF_BOARDNAME]`_
* a GPIO pin, see `[GPIOPMCTRL_BOARDNAME]`_
* a shell script, see `[POWERSHELLSCRIPT_BOARDNAME]`_
* a Shelly device through shelly-ctrl, see `[SHELLY_BOARDNAME]`_
* a tbox SYSTEM Controller Modul through tbox-ctrl (USB HID), see `[TBOX_BOARDNAME]`_
* the DH electronics TM-021 relay module, see `[TM021_BOARDNAME]`_

Loading SPL/U-Boot after power on, or a debugger, with:

* uuu from NXP, see `setup for uuu tool`_
* dfu-util, see `setup for dfu-util tool`_
* sb, xmodem/ymodem over the serial line, see `setup for sb tool`_
* Lauterbach TRACE32, see `setup for Lauterbacher debugger`_
* Segger J-Link, see `setup for Segger debugger`_
* Abatron BDI2000, commands after power on and a telnet session, see
  `setup for BDI2000 debugger`_

It should be easy to extend this! tbot does not prevent you to use
other hardware (nor to make stupid stuff)!

.. _genericconfiguration:

configuration
-------------

Create a directory, e.g. **tbotsetup**, which holds the sources of tbot
and tbottest and a subdirectory **tbotconfig** with all your project
specific settings and testcases. The layout, file by file, is in
`file/directory overview`_; the example is tbottest/tbotconfig.

.. Note::

   You can simply use the script **create_setup.sh** in scripts, which
   will create all files and directories. Start it with the option "--inter"
   and you get asked some questions, which help to make a better basic setup.


.. code-block:: bash

   $ ./scripts/create_setup.sh --inter


start script
............

with the newbot_starter.py script you can start tbot and your setup
without the need to install tbot and tbottest.

tbotconfig
..........

contains the whole lab and board configuration.

README
......

README.BOARDNAME is not mandatory, but it is helpfull to collect/document at least some tbot usecases/commands.

file/directory overview
.......................

What scripts/create_setup.sh sets up, with tbotconfig for one board:

.. code-block:: text

        tbotsetup/
        ├── setup.sh                     aliases for starting tbot (source setup.sh)
        ├── tbot/                        tbot, from github.com/Rahix/tbot, with tbottest/patches applied
        ├── tbottest/                    this repository; newtbot_starter.py starts tbot
        └── tbotconfig/                  your own repository: configuration and testcases
            ├── interactive.py           testcases for interactive sessions
            ├── ci/                      testcases of the tbottest CI on github (only with --ci)
            ├── tc_BOARDNAME.py          testcases of the board
            └── BOARDNAME/
                ├── args/                argumentfiles
                │   ├── argsbase
                │   ├── argsBOARDNAME
                │   ├── argsBOARDNAME-noeth
                │   └── argsBOARDNAME-noeth-ssh
                ├── boardspecific.py     runtime adaptions of the configuration
                ├── BOARDNAME.ini        settings of the board for the testcases
                ├── files/
                │   └── dumpfiles/       files of the register dump testcases
                ├── README.BOARDNAME     notes on the tbot setup of the board
                └── tbot.ini             lab host, build hosts, console, power, ...

.. csv-table:: files and directories
        :header: "Name", "content", "fastlink to documentation"

        "setup.sh", "aliases for starting tbot", "`tbottest/tbotconfig/setup.sh <https://github.com/hsdenx/tbottest/blob/master/tbottest/tbotconfig/setup.sh>`__"
        "tbotconfig/interactive.py", "testcases for interactive sessions: lab host, build host, kas shell, board, U-Boot, Linux, BDI2000", ""
        "tbotconfig/ci", "testcases the github CI of tbottest runs; create_setup.sh copies them only with ``--ci``", ""
        "tbotconfig/tc_BOARDNAME.py", "testcases of the board, from tbottest/tbotconfig/BOARDNAME/BOARDNAME.py", ""
        "BOARDNAME/args", "argumentfiles: argsbase, argsBOARDNAME, and the variants -noeth (flags noethinit, noboardethinit) and -noeth-ssh (adds nopoweroff, always-on, ssh, nouboot)", "`argumentfiles`_"
        "BOARDNAME/boardspecific.py", "functions that adapt the configuration at runtime, e.g. replace the @@...@@ placeholders", ":ref:`boardspecificruntimeadaption`"
        "BOARDNAME/BOARDNAME.ini", "ini file with the board specific settings for the generic testcases", "`boardconfiguration file`_"
        "BOARDNAME/files/dumpfiles", "reference files of the register dump testcases (lnx_dump_files in BOARDNAME.ini)", ""
        "BOARDNAME/README.BOARDNAME", "notes on the tbot setup of the board, not mandatory", ""
        "BOARDNAME/tbot.ini", "ini file for lab host, build hosts and how tbot reaches and controls the board", "`tbot ini file (tbot.ini)`_"
        "BOARDNAME/tbot.ini-<id>, BOARDNAME/BOARDNAME.ini-<id>", "copies tbot writes at every start, with the placeholders replaced; flag tmpfilepath:<dir> writes them elsewhere", "`tbot flags`_"

tbot ini file (tbot.ini)
........................

we use for configuring lab and board settings with:

https://docs.python.org/3/library/configparser.html

Find an example file here: `tbottest/tbotconfig/BOARDNAME/tbot.ini
<https://github.com/hsdenx/tbottest/blob/master/tbottest/tbotconfig/BOARDNAME/tbot.ini>`_

Currently there are the following sections in tbot.ini:

[LABHOST]
^^^^^^^^^

here you configure common lab host setting. Mandatory.

You can select between ssh key login or password login
into the lab host.

For login with ssh key set key 'sshkeyfile', for password login set key 'password'.

.. csv-table:: [LABHOST]
        :header: "key", "value", "example"

        "labname", "name of your lab", "lab7"
        "hostname", "hostname of lab host", "192.168.1.123"
        "username", "username on lab host", "pi"
        "port", "ssh port number", "22"
        "sshkeyfile", "path to the ssh keyfile, tbot uses", "/home/USERNAME/.ssh/id_rsa"
        "password", "set password to login into lab host", "FooBar"
        "date", "subdirectory in boards tftp path", "20210803-ml"
        "shelltype","type of the linux shell (bash|ash)","bash"
        "toolsdir", "where does tbot find tools installed on lab host", "/home/USERNAME/source"
        "tftproot", "rootpath to tftp directory on lab host. tbot stores there build results.", "/srv/tftpboot"
        "tftpsubdir", "boards subdir in tftproot", "BOARD/DATE"
        "workdir", "tbots workdirectory on lab host", "/work/USERNAME/tbot-workdir/BOARD"
        "tmpdir", "path to where tbot stores temporary data", "/tmp/tbot/USERNAME/BOARD"
        "testdir", "optional, path where testcases install or build things on the lab host, default workdir/tbottests", "/work/USERNAME/tbot-workdir/BOARD/tbottests"
        "proxyjump", "if set, proxyjump settings for ssh login on lab host", "pi@xeidos.ddns.net"
        "labinit", "array of strings which contains commands, executed when you init the lab. They run once per boot of the lab host, marked by /tmp/tbotlabinitdone; the setup of the board's ethernet devices on the lab host runs once per board, marked by /tmp/tbotlabinitdone-<boardname>. Remove a marker to run its part again", "['sudo systemctl --all --no-pager restart tftpd-hpa']"
        "nfs_base_path", "base path to nfs share on lab host. !! May you have board specific subdir, so use placeholder @@TBOTLABBASENFSPATH@@ in board ini file and replace it in set_board_cfg", "/srv/nfs"
        "uselocking", "use board locking mechanism. You must pass correct locking id for the board with tbot flag lablocking:<lockingid> else tbot will fail.", "yes|no"

The above labhost defintion is the default one, You can add more than
one labhost, simply add them with the following section naming

.. code-block:: ini

   [LABHOST_<NAME_OF_LAB>]


You can now select this lab by adding tbot flag

.. code-block:: bash

   -f labname:<NAME_OF_LAB>

on start of tbot.


[BUILDHOST]
^^^^^^^^^^^

here you configure common build host setting. Only used, if you use a buildhost.

.. csv-table:: [BUILDHOST]
        :escape: '
        :header: "key", "value", "example"

        "name", "name of your build host", "threadripper-big-build"
        "username", "username on your build host", "hs"
        "hostname", "hostname of your build machine", "192.168.1.120"
        "port", "portnumber of your build machine", "12004"
        "docker", "porxy jump configuration", "hs@192.168.1.120:22"
        "dl_dir", "for yocto builds, sets DL_DIR", "/work/downloads"
        "sstate_dir", "for yocto builds, set SSTATE_DIR", "/work2/hs/tbot2go/yocto-sstate"
        "kas_ref_dir", "when using kas, path where kas finds git trees for reference cloning", "/work/hs/src"
        "workdir", "path to directory where tbot can work on", "/work/big/hs/tbot2go"
        "testdir", "optional, path where testcases install or build things on the build host, e.g. an SDK, default workdir/tbottests", "/work/big/hs/tbot2go/tbottests"
        "authenticator", "path to ssh id key file", "/home/hs/.ssh/id_rsa"
        "password", "password for ssh login. Unsure!", "CrazyPassword"
        "initcmd", "list of commands executed after login", "['"uname -a'", '"cat /etc/os-release'"]"


If you do not add **authenticator** or **password**, tbot uses
**NoneAuthenticator** for ssh login. Hopefully than your ssh config
is correct.

The above buidlhost defintion is the default one, You can add more than
one buildhost, simply add them with the following section naming

.. code-block:: ini

   [BUILDHOST_<NAME_OF_BUILDER>]


You can now select this builder by adding tbot flag

.. code-block:: bash

   -f buildname:<NAME_OF_BUILDER>

on start of tbot.


The next sections depend on your board configuration

[BOOTMODE_BOARDNAME]
^^^^^^^^^^^^^^^^^^^^

if you need to set a bootmode for your board, you can add this section.

You can give each bootmode a name and if you pass this name
to tbot with the "-f" flag, the lab approach first
sets all gpios you have defined for this bootmode to the
respective states, before it powers on the board.

Find more information in

:py:meth:`tbottest.labgeneric.GenericLab.set_bootmode`

[PICOCOM_BOARDNAME]
^^^^^^^^^^^^^^^^^^^

if you want to use picocom for connecting to your boards console.

:py:meth:`tbottest.connector.PicocomConnector`

replace BOARDNAME with the name of your board!
Here as example wandboard.

.. csv-table:: [PICOCOM_wandboard]
        :header: "key", "value", "example"

        "baudrate", "baudrate of the boards console", "115200"
        "device", "linux device name for the serial device on lab host", "/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller-if00-port0"
        "delay", "delay for power off", "3"
        "noreset", "set picocom noreset parameter", "True"
        "slow_send_delay", "optional, seconds to wait after each chunk sent to the console", "0.01"
        "slow_send_chunksize", "optional, maximum number of bytes sent at once", "1"

Without ``slow_send_delay`` and ``slow_send_chunksize`` the channel sends
8 bytes and then waits 10 ms. Consoles that still drop characters (the
echo of a command misses letters) need smaller chunks, down to 1.


[KERMIT_BOARDNAME]
^^^^^^^^^^^^^^^^^^

if you want to use kermit for connecting to your boards console

:py:meth:`tbottest.connector.KermitConnector`

replace BOARDNAME with the name of your board!
Here as example wandboard.

.. csv-table:: [KERMIT_wandboard]
        :header: "key", "value", "example"

        "cfgfile", "path to kermit config file, which is passed to kermit when starting", "/home/pi/kermrc_wandboard"
        "delay", "delay for poweroff", "3"
        "kermit_options", "optional, additional command line options passed to kermit before the config file", "['-c', '-y']"

[SCRIPTCOM_BOARDNAME]
^^^^^^^^^^^^^^^^^^^^^

if you want to use a script for connecting to your boards console.

:py:meth:`tbottest.connector.ScriptConnector`

replace BOARDNAME with the name of your board!
Here as example wandboard.

.. csv-table:: [SCRIPTCOM_wandboard]
        :header: "key", "value", "example"

        "scriptname", "Name of the script", "connect"
        "exitstring", "string send to exit", "~~."


[TELNET_BOARDNAME]
^^^^^^^^^^^^^^^^^^

if you want to use telnet for connecting to your boards console
(e.g. a terminal/console server exposing the serial line as a telnet
port).

:py:meth:`tbottest.connector.TelnetConnector`

replace BOARDNAME with the name of your board!
Here as example wandboard.

.. csv-table:: [TELNET_wandboard]
        :header: "key", "value", "example"

        "host", "optional, telnet host", "localhost"
        "port", "telnet port", "2013"
        "delay", "optional, delay after exit", "3"


[GPIOPMCTRL_BOARDNAME]
^^^^^^^^^^^^^^^^^^^^^^

If you want to control boards power with gpio pins


replace BOARDNAME with the name of your board!
Here as example wandboard.

.. csv-table:: [GPIOPMCTRL_wandboard]
        :header: "key", "value", "example"

        "gpiopmctl_pin", "pin number of gpio pin", "17"
        "gpiopmctl_state", "on state", "1"

[POWERSHELLSCRIPT_BOARDNAME]
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you want to control boards power with a shell script

:py:meth:`tbottest.powercontrol.PowerShellScriptControl`

replace BOARDNAME with the name of your board!
Here as example wandboard.

.. csv-table:: [POWERSHELLSCRIPT_wandboard]
        :header: "key", "value", "example"

        "script", "Name of shell script used to control board power", "/tmp/power.sh"



[SISPMCTRL_BOARDNAME]
^^^^^^^^^^^^^^^^^^^^^

If you want to control boards power with sispmctl

:py:meth:`tbottest.powercontrol.SispmControl`

replace BOARDNAME with the name of your board!
Here as example wandboard.

.. csv-table:: [SISPMCTRL_wandboard]
        :header: "key", "value", "example"

        "device", "id of sispmctl device", "01:01:4f:d4:b1"
        "port", "sispmctl port used for the boards power", "3"

[SHELLY_BOARDNAME]
^^^^^^^^^^^^^^^^^^

If you want to control boards power with a Shelly device. tbot calls
`shelly-ctrl <https://github.com/EmbLux-Kft/shelly-ctrl>`_ on the lab
host, which must reach the Shelly device. Without ``command`` tbot uses
``shelly-ctrl.py`` from the PATH of the lab host, else shelly-ctrl in
``shelly-ctrl`` in the ``toolsdir`` of the lab host. If it is in neither
place, tbot clones it into this directory and installs its python
dependencies into a virtual environment ``.venv`` in it, so the lab host
needs git and python3 with the venv module. With ``install = no`` tbot
stops instead. tbot looks for shelly-ctrl only once per run.

:py:meth:`tbottest.powercontrol.ShellyControl`

replace BOARDNAME with the name of your board!
Here as example wandboard.

.. csv-table:: [SHELLY_wandboard]
        :header: "key", "value", "example"

        "device", "Shelly device, given by IP, by MAC or by its mDNS name", "192.168.1.86"
        "id", "optional channel of multi channel devices, default 0", "0"
        "command", "optional shelly-ctrl command on the lab host, it is not installed by tbot", "shelly-ctrl.py"
        "timeout", "optional maximum time in seconds to look up MAC or mDNS name", "5"
        "install", "optional, no if tbot should not install shelly-ctrl, default yes", "no"

[TBOX_BOARDNAME]
^^^^^^^^^^^^^^^^

If you want to control boards power with a tbox SYSTEM Controller
Modul (talking to it over USB HID via tbox-ctrl)

:py:meth:`tbottest.powercontrol.TboxCtrlControl`

replace BOARDNAME with the name of your board!
Here as example wandboard.

.. csv-table:: [TBOX_wandboard]
        :header: "key", "value", "example"

        "powerpin", "tbox-firmware pin to switch for this board", "P1_5V_EN"
        "vid", "optional USB VID override for tbox-ctrl", "0x1209"
        "pid", "optional USB PID override for tbox-ctrl", "0x0001"

[TM021_BOARDNAME]
^^^^^^^^^^^^^^^^^

Set this section, If you want to control boards power with DH electronics
"TM-021 4-fach Relaismodul".

:py:meth:`tbottest.powercontrol.TM021Control`

replace BOARDNAME with the name of your board!
Here as example wandboard.

.. csv-table:: [TM021_wandboard]
        :header: "key", "value", "example"

        "device", "device node of used linux device", "/dev/relais"
        "baudrate", "baudrate for the linux device", "500000"
        "timeout", "timeout in seconds for one command", "5"
        "address", "address of the relais", "0"
        "port", "port of the relais", "1"
        "debug", "if you want to have debug traces set this to True", "False"


[TF_BOARDNAME]
^^^^^^^^^^^^^^

If you want to control boards power with tinkerforge

:py:meth:`tbottest.powercontrol.TinkerforgeControl`

replace BOARDNAME with the name of your board!
Here as example wandboard.

.. csv-table:: [TF_wandboard]
        :header: "key", "value", "example"

        "uid", "tinkerforges uid", "Nt2"
        "channel", "channel", "1"

ethernet config
^^^^^^^^^^^^^^^

ipsetup for an ethernetdevice on board, add section

[IPSETUP_BOARDNAME_<ethdevice_board>]
:::::::::::::::::::::::::::::::::::::

replace BOARDNAME with the name of your board!
Here as example for setup eth0 on wandboard.

.. csv-table:: [IPSETUP_wandboard_eth0]
        :header: "key", "value", "example"

        "labdevice", "device which is connected to eth0 on board", "eth0"
        "netmask", "netmask", "255.255.255.0"
        "ethaddr", "ethaddr (MAC) of the device on board", "00:1f:7b:b2:00:0e"
        "ipaddr", "ipaddr of the board for device on board", "192.168.3.21"
        "serverip", "server ip, ip address of lab host", "192.168.3.1"

[UBCFG_BOARDNAME]
:::::::::::::::::

if you need to specifiy in U-Boot which lab host ethernetinterface is should use, define
this section.

replace BOARDNAME with the name of your board!
Here as example for setup eth0 on wandboard.

.. csv-table:: [UBCFG__wandboard]
        :header: "key", "value", "example"

        "ethintf", "ethernetinterface used on lab host for u-boot, default is eth0", "eth0"

setup for dfu-util tool
^^^^^^^^^^^^^^^^^^^^^^^

if you need to load U-Boot binaries with dfu-util tool, use

:py:meth:`tbottest.machineinit.DFUUTIL`

define the section

.. csv-table:: [DFUUTIL_CONFIG_<BOARDNAME>]
        :header: "key", "value", "example"

        "cmds", "array of dictionary, format see example", "[{'a':'@FSBL /0x01/1*1Me', 'D':'${LABHOST:tftproot}/${LABHOST:tftpsubdir}/u-boot-spl.stm32'}, {'a':'u-boot.itb', 'D':'${LABHOST:tftproot}/${LABHOST:tftpsubdir}/u-boot.itb'}]"


setup for uuu tool
^^^^^^^^^^^^^^^^^^

if you want to use NXPs uuu tool with class

:py:meth:`tbottest.machineinit.UUULoad`

define the section


.. csv-table:: [UUU_CONFIG__wandboard]
        :header: "key", "value", "example"

        "cmd", "comma seperated list of uuu commands to load SPL/U-Boot with uuu tool.", "LBD/SPL,SDPV: delay 100,SDPV: write -f LBD/u-boot.img -addr 0x877fffc0,SDPV: jump -addr 0x877fffc0"

setup for sb tool
^^^^^^^^^^^^^^^^^

if you need to use UART boot and xmodem / ymodem transfer
for loading the bootloader onto the hardware use this class

:py:meth:`tbottest.machineinit.XMODEMLoad`

define the section

.. csv-table:: [XMODEM_CONFIG__wandboard]
        :header: "key", "value", "example"

        "device", "serial device sb tool uses", /dev/ttyUSB0
        "cmd", "list of commands to load SPL/U-Boot with sb tool.", ["sb --xmodem TFTPDIR/tiboot3.bin > SERDEV < SERDEV"]

SERDEV is replaced before executing the command with the value in device
and TFTPDIR is replaced with the boards current tftp path.


setup for Lauterbacher debugger
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

if you want to use Lauterbacher debugger use this class

Currently we use the python script t32apicmd.py
from lauterbach installation directory "install_path" in
subdir "demo/api/python". Later we will use this api directly.

:py:meth:`tbottest.machineinit.LauterbachLoad`

define the section

.. csv-table:: [LAUTERBACH_CONFIG_wandboard]
        :header: "key", "value", "example"

        "verbose", "1 = verbose output", "1"
        "cmd", "", "/opt/t32/bin/pc_linux64/t32marm-qt"
        "install_path", "path to your installation of Lauterbacher tools", "/opt/t32"
        "config", "path to config.t32 file", "/from_ftp/lauterbach-scripts/hsconfig.t32"
        "script", "path to script which gets executed", "/from_ftp/lauterbach-scripts/autostart.cmm"

setup for Segger debugger
^^^^^^^^^^^^^^^^^^^^^^^^^

if you want to use Segger debugger use this class

:py:meth:`tbottest.machineinit.SeggerLoad`

define the section

.. csv-table:: [SEGGER_CONFIG_wandboard]
        :header: "key", "value", "example"

        "install_path", "path to your installation of the Segger tools", "/opt/segger"
        "cmds", "list of commands executed in JLinkExe shell to bring up U-Boot", "[{'cmd':'go', 'prompt':'J-Link>'}]"

setup for BDI2000 debugger
^^^^^^^^^^^^^^^^^^^^^^^^^^

if your board has an Abatron BDI2000 attached, define its address. tbot
then provides the BDI2000 as a machine for the role
:py:class:`tbottest.bdi2000.BDI2000`, a telnet session to the BDI's command
line from the lab host, on which ``exec()`` runs one BDI command and
returns its output.

Open an interactive session on it with the testcase

:py:func:`tbottest.tc.bdi2000.bdi2000`

Leave it like any other interactive session, with CTRL+] three times within
one second.

With ``poweron_cmds`` set, the board control runs these commands on the
BDI2000 every time it has powered the board on, for example ``reset run``
when the BDI would otherwise hold the CPU in reset
(:py:class:`tbottest.machineinit.BDI2000Cmds`). Right after power on the
BDI still waits for the target Vcc and a command sent then is lost; with
``poweron_wait_state`` set, the commands are only sent once the BDI command
``info`` reports that target state.

After ``reset`` the BDI works through the init list of its configuration
file, but prints its prompt before it is done. A command whose output shows
the init list started waits until the BDI reports it ``passed`` (and fails if
it reports ``failed``), so ``poweron_cmds = ["reset", "go 0x40000100"]``
starts the target only after the init list ran.

``poweron_cmds`` can also be a dictionary of named command lists, for a
board that is started in more than one way. The tbot flag
``-f poweron_cmds:<name>`` selects the list to run; without the flag the
entry ``default`` is taken, and no commands at all if there is none.
``-f poweron_cmds:None`` skips the BDI2000 after power on completely,
``poweron_wait_state`` included, for example when the board is started by
hand on the BDI (:py:func:`tbottest.initconfig.bdi2000_poweron_cmds`).

.. code-block:: ini

    poweron_cmds = {
        "default": ["reset run"],
        "nowdt": ["reset", "go 0x40000100"],
        }

A list may contain the entry ``configname:<file>``, the configuration
file the BDI has to run with for the other commands. It is not sent as a
command: before the other commands, the board control asks the BDI with
``config`` which file it runs with. If it is ``<file>``, the commands run
as usual. Otherwise it sets ``<file>`` with ``config <file> <host>``, the
host being the one the BDI loads its current file from. The BDI answers
``Updating configuration passed. Booting .....``, boots with the new file
right away and ends the telnet session; tbot connects again until the BDI
answers, within ``poweron_timeout`` seconds, and checks that it runs with
``<file>`` before it waits for
``poweron_wait_state`` and sends the commands
(:py:func:`tbottest.bdi2000.ensure_config`). So each command list can
bring the configuration file it needs:

.. code-block:: ini

    poweron_cmds = {
        "default": ["configname:amc/bdi/tqm855-AMC-nowdt.cfg", "reset", "go 0x40000100"],
        "reset": ["configname:amc/bdi/tqm855-AMC.cfg", "reset run"],
        }

.. csv-table:: [BDI2000_<boardname>]
        :header: "key", "value", "example"

        "ip", "IP address of the BDI2000, reached with telnet from the lab host", "192.168.3.101"
        "poweron_cmds", "optional list of BDI commands run after each power on of the board, or a dictionary of such lists selected with -f poweron_cmds:<name>; an entry configname:<file> selects the configuration file of the BDI first", "['reset run']"
        "poweron_wait_state", "optional target state, as info reports it, to wait for before poweron_cmds", "debug mode"
        "poweron_timeout", "seconds to wait for poweron_wait_state, and for the BDI to boot for configname:<file>, default 30", "30"

.. _boardspecificruntimeadaption:

boardspecfic runtime adaptions
..............................

The ini file approach is static, which means we cannot change
configuration @runtime. This generic approach searches in **tbotconfig**
for a **boardspecific.py** file, which can contains several
functions, the generic approach tries to call.

In this functions you can adapt settings dependend on the usecase.
Or may do special stuff in machine shells.

In the default ini files there are placeholders beginning with **@@**
and ending with **@@**. You can easily replace them with
:ref:`iniconfighelperfunctions`.

Therefore the following functions are used:

set_board_cfg(temp: str = None, filename: str = None)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This file is called early in bootup before any ini file
is parsed. So you can adapt the ini files for your needs

.. code-block:: python

    import tbot
    from tbottest.generic.iniconfig import replace_in_file

    tbot.selectable.printed = False

    def print_log(msg):
         if tbot.selectable.printed:
                return

            tbot.log.message(tbot.log.c(msg).yellow)

    def set_board_cfg(temp: str = None, filename: str = None):
        """
        setup board specific stuff in ini files before they get parsed
        """
        # print tbot.flags, as tbot prints them not longer
        print_log(f"TBOT.FLAGS {tbot.flags}")

        replace_in_file(filename, "@@TBOTBOARD@@", "<boardname in your lab setup>")
        replace_in_file(filename, "@@TBOTDATE@@", "20230221")
        replace_in_file(filename, "@@TBOTMACHINE@@", "<yocto machine name>")

        tbot.selectable.boardname = None
        for f in tbot.flags:
            if f.startswith("boardname:"):
                tbot.selectable.boardname = f.split(":", 1)[1]

        if tbot.selectable.boardname == None:
            tbot.selectable.boardname = "wandboard"


board_set_boardname
^^^^^^^^^^^^^^^^^^^

called from initconfig.py generic_get_boardname()

.. code-block:: python

    import tbot


    def board_set_boardname() -> str:
        # do not use boardname flag
        BOARDNAME = "foo"
        for f in tbot.flags:
            if "8G" in f:
                if len(f) == 2:
                    BOARDNAME = "foo-8G"

        return BOARDNAME


set_ub_board_specific
^^^^^^^^^^^^^^^^^^^^^

called from boardgeneric.py in init function.

setup U-Boot specific parts after entering the U-Boot shell

.. code-block:: python

    def set_ub_board_specific(self):
        optargs = self.env("optargs")
        optupd = False
        if "bootchartd" in tbot.flags:
            optargs = f"{optargs} init=/lib/systemd/systemd-bootchart"
            optupd = True

        if "debug_initcalls" in tbot.flags:
            optargs = f"{optargs} initcall_debug"
            optupd = True

        if optupd == True:
            self.env("optargs", optargs)

        if "silent" in tbot.flags:
            self.env("console", "silent")


boardconfiguration file
.......................

we use for configuring for boardspecific testcasesettings with:

https://docs.python.org/3/library/configparser.html

add therefore a BOARDNAME.ini file must exist in tbotconfig/BOARDNAME

It contains two sections:

```TC_BOARDNAME``` and ```TC```

see also:
:py:func:`tbottest.initconfig.init_get_config`

from where the generic board testcase approach boardgeneric.py
takes the config to generate the class GenericBoardConfig,
used from generic testcases.

common settings
^^^^^^^^^^^^^^^

common settings for your board.

.. csv-table:: [TC]
        :header: "key", "description", "default", "example"

        "tmpdir", "path to place on board, which could be used for temporary data testcases need.", "/tmp", "/tmp/tbot"
        "death_strings", "array of strings, which should not ocur in stream", "[]", "['Kernel panic']"

u-boot settings
^^^^^^^^^^^^^^^

settings needed for U-Boot testcases.

.. csv-table:: [TC]
        :header: "key", "description", "default", "example"

        "uboot_boot_timeout", "config boot_timeout, set None if None", "90", "None"
        "uboot_autoboot_keys","string with which U-Boot boot is interrupted. It is possible to set also a bytearray, see the table below","None","SPACE"
        "uboot_autoboot_prompt","regular expression of the U-Boot autoboot prompt, None if U-Boot prints none","autoboot:\s{0,5}\d{0,3}\s{0,3}.{0,80}","None"
        "uboot_autoboot_timeout","UBootAutobootInterceptSimple timeout for waiting for U-Boot prompt","0.1","0.05"
        "uboot_has_retcode", "tbot reads the return code of every U-Boot command with echo $?, which only the hush parser supports. Set to False for a U-Boot without hush: exec() then skips that query and reports 0, so exec0() cannot detect a failing command", "True", "False"
        "rescueimage", "name of rescueimage", "None", "rescueimage-fit.itb"
        "qspiheader", "name of qspi header", "None", "qspiheader.bin"
        "splimage", "name of spl image", "None", "SPL"
        "fb_res_setup", "u-boot commands for setting up rescue image boot with fastboot and uuu tool", "None", "run ramargs addcon addmtd addopt"
        "fb_res_boot", "u-boot command for booting rescue image with fastboot and uuu tool", "None", "bootm 94000000"
        "fb_cmd", "fastboot init command", "None", "fastboot usb 0"
        "ub_env","list dict of u-boot environment variables which get set after login into u-boot","[]","[{""name"":""optargs"", ""val"":""earlycon clk_ignore_unused""}]"

.. csv-table:: uboot_autoboot_keys example
        :escape: '
        :header: "configuration string", "sended bytes to console"

        "K", "\x4b"
        "SPACE", "\x03"
        "bytearray:1b1b", "\x1b\x1b"

linux settings
^^^^^^^^^^^^^^

settings needed for linux testcases.

.. csv-table:: [TC]
        :header: "key", "description", "default", "example"

        "linux_user", "username for linux login. Set to empty (linux_user = ) to just send Enter instead of a username, e.g. for boards that already auto-login", "root", "root"
        "linux_password", "password for linux login, None for no password required", "None", "None"
        "linux_login_prompt", "prompt that indicates tbot should send the username. Set this to match your board's shell prompt if it logs in automatically and never shows a real login prompt. Matched as regex with optional trailing whitespace, no need to (and can't, ini strips it) include a trailing space", "login: ", "root@foobar:~#"
        "linux_login_delay", "login delay in seconds", "5", "1"
        "linux_boot_timeout", "Maximum time for Linux to reach the login prompt.", "None", "30"
        "linux_init_timeout", "If not None, timeout in seconds after ethernetconfig", "None", "2.0"
        "linux_netcmd", "command the ethernet setup after login uses: auto takes ip if the board has it (checked once with command -v ip), else ifconfig; ip or ifconfig always take that one. The flag useifconfig takes ifconfig in any case", "auto", "ifconfig"
        "linux_init","list of commands send after login. mode = exec or exec0","[]","[{""mode"":""exec0"", ""cmd"":""echo Hallo""}]"
        "testdir", "directory on the board for what testcases put there; in the root filesystem if a testcase puts files there through an NFS root", "/run/tbot-testdata/tbottests", "/home/root/tbottests"
        "shelltype", "linux login shell type (bash|ash)", "ash", "bash"
        "linux_plain_prompt", "True gives the interactive linux shell a plain <name>> prompt, without the color escapes and the directory that an old busybox ash prints literally (tbot's interactive_plain_prompt)", "False", "True"
        "beep","list of dictionary of commands for beep command","[]","[{""freq"": ""440"", ""length"":""1000""}]"
        "cyclictestmaxvalue", "maximum allowed value from stress-ng 'Max' colum", "100", "cyclictestmaxvalue = 100"
        "dmesg","list of strings, which should be in dmesg output","[]","dmesg = [""OF: fdt: Machine model:"", ""gpio-193 (eeprom-wc): hogged as output/low"",]"
        "dmesg_false","list of strings, which should be not in dmesg output","[]","dmesg_false = [""crash""]"
        "iperf","list of dictionary for iperf test","[]","iperf = [{""intervall"":""1"",""minval"":""290000000"",""cycles"":""30""}]"
        "leds","list of dictionary for checking leds","[]","leds = [{""path"":""/sys/class/leds/led-orange"", ""bootval"":""0"", ""onval"":""1""},]"
        "lnx_commands","list of dictionary for checking linux commands","[]","lnx_commands = [{""cmd"":""<your linux command>"", ""val"":""<string which is in output of command> or undef""},]"
        "network_iperf_intervall", "iperf intervall", "1", "network_iperf_intervall = 1"
        "network_iperf_minval", "iperf minimum network throughput", "1", "network_iperf_minval = 9000000"
        "network_iperf_cylces", "iperf cycles", "1", "network_iperf_cycles = 30"
        "nvramdev", "nvram device", "6", "nvramdev = 6"
        "nvramcomp", "compatibility string of nvram device", "microchip,48l640", "nvramcomp = 'microchip,48l640'"
        "nvramsz", "size of nvram device", "8192", "nvramsz = 8192"
        "ping","list of dict for ping config.","[]","ping = [{""ip"":""${default:serverip}"",""retry"":""10""}]"
        "regdump","list of dict for generic regdump","[]","regdump = [{""address"":""0x30340004""}, {""address"":""0x30330070""}]"
        "rs485labdev","path to device","/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_AB0PI210-if00-port0","rs485labdev = ""/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_AB0PI210-if00-port0"""
        "rs485baud","baudrate used for test","115200","rs485baud = ""115200"""
        "rs485boarddev","list of strings, each string contains a path to device which used in test","[""/dev/ttymxc2""]","rs485boarddev = [""/dev/ttymxc2""]"
        "rs485lengths","list of strings. Each string is a length of data send over rs485 line","[""20"", ""100"", ""1024""]","rs485lengths = [""20"", ""100"", ""1024""]"
        "sensors","list of dictionary for checking temperature sensors","[]","sensors = [{""path"":""/sys/class/hwmon/hwmon0"", ""name"":""tmp102"", ""tmpvalues"":[{""valname"":""temp1_input"", ""min"":""0"", ""max"":""100000""}]},]"
        "mtd_parts","list of dictionary for MTD parts definition","[]","mtd_parts = [{""name"":""SPL"", ""size"":""10000""},]"
        "ub_mtd_delete","list of strings with MTD names which are allowed to delete","[]","ub_mtd_delete = [""SPL"", ""uboot""]"
        "ssh_keyfile","ssh setup: authentication using private key file ssh_keyfile","None","/home/{user}/.ssh/id_rsa"
        "ssh_password","ssh setup: set password for password ssh login","None","foobar"


swupdate settings
^^^^^^^^^^^^^^^^^

settings needed for swupdate testcases.

.. csv-table:: [TC]
        :header: "key", "description", "default", "example"

        "swuethdevice", "device which is used for getting ethernetconfiguration on lab host", "eth0", "eth0"
        "swuimage", "Name of swu image name which get installed on board", "mandatory, no fallback", "swu-image.swu"

kas settings
^^^^^^^^^^^^

settings needed for yocto build with kas tool.

.. csv-table:: [TC]
        :header: "key", "description", "default", "example"

        "kas", "dictionary with values need for class KAS, see :py:class:`tbottest.tc.kas.KAS`", "mandatory, no default", "see: tbottest/tbotconfig/BOARDNAME.ini"
        "kas_check_files", "list of files, which must exist after building", "[]", "['tmp/deploy/images/wandboard/SPL']"
        "kas_results", "list of files, which get copied from build host to lab host for later use. Basepath is machine directory in tmp/deploy/images", "[]", "['SPL']"

Inside the kas dictionary, kas_mounts adds directories of the build host to
the kas container, each as host:container or host:container:options, for
example a directory with build helper scripts. See
:py:class:`tbottest.tc.kas.KAS`.

With tbot flag kaskeepconfig, kas keeps the repo checkouts and build/conf as
they are (kas --keep-config-unchanged): tbot does no kas checkout and passes
the option to kas shell and kas build. It needs one earlier run without the
flag, which set the build tree up.

argumentfiles
.............

it is convenient to collect tbot arguments in argumentsfile. As you
will have a lot of tbot arguments. We start in this example with
a base "argsBOARDNAME" file, which than other files include.

.. note::

    You can use shell variables also in argumentfiles!

``newtbot_starter.py`` sets ``TBOT_STARTTIME`` to the start time of the
run, ``YYYYMMDD-HHMMSS``, if it is not set already. With it, every run
writes its log to a file of its own, here in ``log/`` below the directory
tbot is started from, which has to exist:

.. code-block:: bash

    --json-log-stream
    log/${TBOT_STARTTIME}.log

The following example uses piccom for accessing serial console and
sispmctl for boards power control.

If you have another setup, adapt this "base" argument file accordingly.

For example, if you want to use kermit for accessing console, remove the
tbot flag piccom (as kermit is default).

If you want to use Tinkerforge for controlling boards power, add flag "tinkerforge"


.. code-block:: shell

   $ cat tbotconfig/BOARDNAME/args/argsBOARDNAME
   @tbotconfig/BOARDNAME/args/argsbase
   -fpicocom

.. note::

   argsbase is a simple copy from tbottest/tbotconfig/BOARDNAME/argsfiles/argsbase

With executing tbot on lab host, you do not need to ssh to lab host,
so use local flag.

.. code-block:: shell

   $ cat config/BOARDNAME/args/argsBOARDNAME-local
   @config/BOARDNAME/args/argsBOARDNAME
   -flocal


If you do not want that tbot always initialize ethernet configuration
on your lab host, use

.. code-block:: shell

    $ cat config/BOARDNAME/args/argsBOARDNAME-local-noeth
    @config/BOARDNAME/args/argsBOARDNAME-local
    -fnoethinit

If you want to login to a board, which is already on and runs linux

.. code-block:: shell

    $ cat config/BOARDNAME/args/argsBOARDNAME-local-noeth-on
    @config/BOARDNAME/args/argsBOARDNAME-local-noeth
    -falways-on
    -fnouboot
    -fnopoweroff

.. note::

    start tbot with flag "always-on" and tbot will not poweroff
    the board when ending, so if you have bootet into linux, and
    logout, linux will remain and tbot can logon again!

    This helps a lot when developing testcases!

.. _argumentfilesshlogin:

Argumentfile for ssh login
^^^^^^^^^^^^^^^^^^^^^^^^^^

If you want to login per ssh into an already running linux on the board

.. code-block:: shell

    $ cat config/BOARDNAME/args/argsBOARDNAME-local-noeth-on
    @config/BOARDNAME/args/argsBOARDNAME-local-noeth
    -fssh


And last but not least, if you have an imx6 based board and want to load
SPL/U-Boot with tbot onto it, start tbot with:

.. code-block:: shell

   $ cat config/BOARDNAME/args/argsBOARDNAME-local-uuu
   @config/BOARDNAME/args/argsBOARDNAME-local
   -fuuuloader


tbot call example

.. code-block:: shell

    $ ./newtbot_starter.py @tbotconfig/BOARDNAME/args/argsBOARDNAME-asus-kirkstone-nfs -f kas tbottest.inter.uboot
    tbot starting ...
    ├─TBOT.FLAGS {'boardfile:tbotconfig/BOARDNAME/BOARDNAME.ini', 'useifconfig', 'bootcmd:tftp_nfs', 'noboardethinit', 'noethinit', 'kas', 'do_power', 'kaslayerbranch:kirkstone', 'inifile:tbotconfig/BOARDNAME/tbot.ini', 'bootmode:emmc', 'picocom'}
    ├─boardname now BOARDNAME
    ├─Using kas file kas-denx-withdldir.yml
    ├─Calling uboot ...
    │   ├─[local] ssh -o BatchMode=yes -i /home/pi/.ssh/id_rsa -p 22 pi@tbotlab
    │   ├─set bootmode bootmode:emmc
    │   ├─[lab8] test -d /sys/class/gpio/gpio14
    │   ├─[lab8] cat /sys/class/gpio/gpio14/direction
    │   │    ## out
    │   ├─[lab8] printf %s 1 >/sys/class/gpio/gpio14/value
    │   ├─[local] ssh -o BatchMode=yes -i /home/pi/.ssh/id_rsa -p 22 pi@BOARDNAMElab
    │   ├─set bootmode bootmode:emmc
    │   ├─[lab8] test -d /sys/class/gpio/gpio14
    │   ├─[lab8] cat /sys/class/gpio/gpio14/direction
    │   │    ## out
    │   ├─[lab8] printf %s 1 >/sys/class/gpio/gpio14/value
    │   ├─[lab8] picocom -r -b 115200 -l /dev/serial/by-id/usb-FTDI_C232HM-EDHSL-0_FT57MR3U-if00-port0
    │   ├─POWERON (board-control-full)
    │   ├─[lab8] sispmctl -D 01:01:4f:09:5b -o 1
    │   │    ## Accessing Gembird #0 USB device 012
    │   │    ## Switched outlet 1 on
    │   ├─UBOOT (BOARDNAME-uboot)
    │   │    <> picocom v3.1
    │   │    <>
    │   │    <> port is        : /dev/serial/by-id/usb-FTDI_C232HM-EDHSL-0_FT57MR3U-if00-port0
    │   │    <> flowcontrol    : none
    │   │    <> baudrate is    : 115200
    │   │    <> parity is      : none
    │   │    <> databits are   : 8
    │   │    <> stopbits are   : 1
    │   │    <> escape is      : C-a
    │   │    <> local echo is  : no
    │   │    <> noinit is      : no
    │   │    <> noreset is     : yes
    │   │    <> hangup is      : no
    │   │    <> nolock is      : yes
    │   │    <> send_cmd is    : sz -vv
    │   │    <> receive_cmd is : rz -vv -E
    │   │    <> imap is        :
    │   │    <> omap is        :
    │   │    <> emap is        : crcrlf,delbs,
    │   │    <> logfile is     : none
    │   │    <> initstring     : none
    │   │    <> exit_after is  : not set
    │   │    <> exit is        : no
    │   │    <>
    │   │    <> Type [C-a] [C-h] to see available commands
    │   │    <> Terminal ready
    │   │    <>
    │   │    <> U-Boot SPL 2023.04 (Apr 03 2023 - 20:38:50 +0000)
    │   │    <> Trying to boot from MMC1
    │   │    <>
    │   │    <>
    │   │    <> U-Boot 2023.04 (Apr 03 2023 - 20:38:50 +0000)
    │   │    <>
    │   │    <> CPU  : AM335X-GP rev 2.1
    │   │    <> Model: XXX
    │   │    <> DRAM:  512 MiB
    │   │    <> Core:  172 devices, 20 uclasses, devicetree: separate
    │   │    <> MMC:   OMAP SD/MMC: 0
    │   │    <> Loading Environment from MMC... OK
    │   │    <> In:    serial@0
    │   │    <> Out:   serial@0
    │   │    <> Err:   serial@0
    │   │    <> Net:   eth2: ethernet@4a100000
    │   │    <> Press SPACE to abort autoboot in 2 seconds
    │   │    <> => <INTERRUPT>
    │   │    <> =>
    │   ├─[BOARDNAME-uboot] setenv serverip 192.168.3.1
    │   ├─[BOARDNAME-uboot] printenv serverip
    │   │    ## serverip=192.168.3.1
    [...]
    │   ├─[BOARDNAME-uboot] printenv optargs
    │   │    ## optargs=consoleblank=0 vt.global_cursor_default=0 lpj=2988032 quiet  rauc.slot=A
    │   ├─Entering interactive shell...
    │   ├─Press CTRL+] three times within 1 second to exit.

    =>

tbot flags
----------

The generic lab and board approach defines some tbot flags, so tbot can handle different usage challenges.
It is recommended to collect arguments in so called argumentsfiles, else you are lost in tbot flags...

======================== ====================================================
tbot flag                Description
======================== ====================================================
always-on                board is already on, log into linux
boardfile                format boardfile:<path>, the board ini file, relative to the tbotconfig directory or absolute; default the BOARDNAME.ini template
boardname                format boardname:<name>, name of the board, used when boardspecific.py does not define board_set_boardname()
bootcmd                  format bootcmd:<real bootcmd>, example bootcmd:net_nfs will execute "run net_nfs"
buildername              format buildername:<name>, select the used build host, section BUILDHOST_<name> in tbot.ini; buildername:local builds on the host tbot runs on
cmdtimestamp             prefix each command log line with a H:M:S timestamp, e.g. [boardname 07:22:26]
dfuutilloader            load SPL/U-Boot with dfu-util tool
do_power                 tbot handles boards power
docker                   if you need to login to a docker container with proxyjump
emmc                     u-boot bootcmd "run boot_emmc" (deprecated, use flag bootcmd)
enterinitramfs           enter initramfs, add enterinitramfs to miscargs (deprecated, use set_ub_board_specific)
gpiopower                use a gpio pin for boards power control
ignore_loglevel          add ignore_loglevel to miscargs (deprecated, use set_ub_board_specific)
inifile                  format inifile:<path>, the tbot.ini file, relative to the tbotconfig directory or absolute; default the tbot.ini template
kas                      u-boot bootcmd "run bootcmdkas"
kaskeepconfig            keep the repo checkouts and build/conf of the kas build as they are, like kas --keep-config-unchanged
kasskipcheckout          skip the kas checkout step
lablockid                format lablockid:<yourlockid>, the lock id for board locking
labname                  format labname:<name of lab host>, select the used lab host (configure in tbot.ini with LABHOST_<name> section)
lauterbachloader         load SPL/U-Boot with Lauterbach TRACE32
lauterbachusesshmachine  with lauterbachloader, run TRACE32 on the SSH machine of tbot.ini instead of the lab host
linux_no_cmd_after_login set nothing after linux login (beside disable clutter)
local                    enable if labhost and tbot host are the same (use SubprocessConnector)
no-bootfit               with ssh, read the board's IP address from "ip route get 1" output that has two spaces before "src"
noboardethinit           do no board ethinit in linux after login
nobootcon                set console to silent (deprecated, use set_ub_board_specific)
noethinit                do not set up the lab host's ethernet devices for the board (lab init)
nopoweroff               do not power the board off
nouboot                  boot into linux without U-Boot interaction; with ssh also without a login on the console
outside                  if lab host is only reachable with proxyjump
panic                    add death string "Kernel panic"
picocom                  use picocom for serial console
poweroffonstart          if set, power off board before powering on
poweron_cmds             format poweron_cmds:<name>, select an entry of the dictionary poweron_cmds in the BDI2000 section of tbot.ini; poweron_cmds:None runs no BDI2000 commands after power on
powershellscript         use a shellscript for boards power control
rescue                   boot rescue system (deprecated, use flag bootcmd)
rescuetftp               boot rescue system, rescue image loaded through tftp (deprecated, use flag bootcmd)
rescueuuu                load the bootloader with the uuu tool and boot into the rescue image loaded with fastboot
scriptcom                use a script for serial console
sdcard                   u-boot bootcmd "run boot_mmc" (deprecated, use flag bootcmd)
seggerloader             use segger debugger for breathing life into board
set-ethconfig            setup ip config in U-Boot
ssh                      login to linux console through ssh (only possible if board already on and in linux)
telnet                   use telnet for serial console
tftpfit                  u-boot bootcmd "run tftp_mmc" (deprecated, use flag bootcmd)
tinkerforge              use tinkerforge for boards power control
tmpfilepath              format tmpfilepath:<directory>, where tbot writes its copies of tbot.ini and the board ini; default next to them
uboot_no_env_set         do not set any U-Boot Environment after U-Boot login
usbloader                load SPL/U-Boot with imx_usb_loader
useifconfig              use ifconfig instead of ip on every machine, also over linux_netcmd of the board ini
uuuloader                load SPL/U-Boot with uuu tool from NXP
xmodemloader             load SPL/U-Boot with sb tool (xmodem/ymodem)
======================== ====================================================
