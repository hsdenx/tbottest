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

serial console access with:

* piccom
* kermit

Powercontrol:

* sispmctl
* TinkerForge
* simple GPIO

It should be easy to extend this! tbot does not prevent you to use
other hardware (nor to make stupid stuff)!

.. _genericconfiguration:

configuration
-------------

Best, use the following directory structure:

.. code-block:: shell

        $ tree .
        tbotconfig
        tbot (checkout from https://github.com/Rahix/tbot)
        tbottest (this repo, checkout from github)

Create for your tbot configuration and own testcases your own repo
**tbotconfig** and use the following directory structure there:

.. code-block:: shell

        $ tree -I log*
        newtbot_starter.py
        tbotconfig
        └── BOARDNAME
            ├── args
            │   ├── argsbase (from tbottest/tbotconfig/BOARDNAME/args/argsbase, replace BOARDNAME with real name)
            │   ├── argsBOARDNAME
            │   └── [...]
            ├── boardspecific.py
            ├── README.BOARDNAME
            ├── tbot.ini
            ├── BOARDNAME.ini

see example in tbottest/tbotconfig.

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

.. csv-table:: subdirectories
        :header: "Name", "content", "fastlink to documentation"

        "args", "contains tbot arguments files, for easier usage", "`argumentfiles`_"
        "tbot.ini", "init file for easy configuration", "`tbot ini file (tbot.ini)`_"
        "BOARDNAME.ini", "init file with boardspecific onfigs for generic testcases", "boardconfiguration file"

tbot ini file (tbot.ini)
........................

we use for configuring lab and board settings with:

https://docs.python.org/3/library/configparser.html

Find an example file here: tbottest:/tbottest/tbotconfig/BOARDNAME/tbot.ini

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
            if "selectableboardname" in f:
                tbot.selectable.boardname = f.split(":")[1]

        if tbot.selectable.boardname == None:
            tbot.selectable.boardname = "wandboard"


board_set_boardname
^^^^^^^^^^^^^^^^^^^

called from initconfig.py generic_get_boardname()

.. code-block:: python

    import tbot


    def board_set_boardname() -> str:
        # do not use selectableboardname flag
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


Currently there are the following sections in tbot.ini:

tbot.ini sections
.................

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
        "shelltype", "type of the linux shell (bash|ash)"
        "toolsdir", "where does tbot find tools installed on lab host", "/home/USERNAME/source"
        "tftproot", "rootpath to tftp directory on lab host. tbot stores there build results.", "/srv/tftpboot"
        "tftpsubdir", "boards subdir in tftproot", "BOARD/DATE"
        "workdir", "tbots workdirectory on lab host", "/work/USERNAME/tbot-workdir/BOARD"
        "tmpdir", "path to where tbot stores temporary data", "/tmp/tbot/USERNAME/BOARD"
        "proxyjump", "if set, proxyjump settings for ssh login on lab host", "pi@xeidos.ddns.net"
        "labinit", "array of strings which contains commands, executed when you init the lab", "['sudo systemctl --all --no-pager restart tftpd-hpa']"
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


[GPIOPMCTRL_BOARDNAME]
^^^^^^^^^^^^^^^^^^^^^^

If you want to control boards power with gpio pins


replace BOARDNAME with the name of your board!
Here as example wandboard.

.. csv-table:: [GPIOPMCTRL_wandboard]
        :header: "key", "value", "example"

        "pin", "pin number of gpio pin", "17"
        "state", "on state", "1"

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
        :escape: '
        :header: "key", "description", "default", "example"

        "uboot_boot_timeout", "config boot_timeout, set None if None", "90", "None"
        "uboot_autoboot_keys", "string with which U-Boot boot is interrupted. It is possible to set also a bytearray", "SPACE", "None"
        "autoboot_prompt", "set autoboot_prompt, None if None", b'"autoboot:\\s{0,5}\\d{0,3}\\s{0,3}.{0,80}'", "None"
        "autoboot_timeout", "UBootAutobootInterceptSimple timeout for waiting for U-Boot prompt", '0.05', "0.1"
        "rescueimage", "name of rescueimage", "None", "rescueimage-fit.itb"
        "qspiheader", "name of qspi header", "None", "qspiheader.bin"
        "splimage", "name of spl image", "None", "SPL"
        "fb_res_setup", "u-boot commands for setting up rescue image boot with fastboot and uuu tool", "None", "run ramargs addcon addmtd addopt"
        "fb_res_boot", "u-boot command for booting rescue image with fastboot and uuu tool", "None", "bootm 94000000"
        "fb_cmd", "fastboot init command", "None", "fastboot usb 0"
        "ub_env", "list dict of u-boot environment variables which get set after login into u-boot", "[]", "[{'"name'":'"optargs'", '"val'":'"earlycon clk_ignore_unused'"}]"

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
        :escape: '
        :header: "key", "description", "default", "example"

        "linux_user", "username for linux login", "root", "root"
        "linux_password", "password for linux login, None for no password required", "None", "None"
        "linux_login_delay", "login delay in seconds", "5", "1"
        "linux_boot_timeout", "Maximum time for Linux to reach the login prompt.", "None", "30"
        "linux_init_timeout", "If not None, timeout in seconds after ethernetconfig", "None", "2.0"
        "linux_init", "list of commands send after login. mode = exec or exec0", "[]", "[{'"mode'":'"exec0'", '"cmd'":'"echo Hallo'"}]"
        "shelltype", "linux login shell type (bash|ash)", "ash", "bash"
        "beep", "list of dictionary of commands for beep command", "[]", "[{'"freq'": '"440'", '"length'":'"1000'"}]"
        "cyclictestmaxvalue", "maximum allowed value from stress-ng 'Max' colum", "100", "cyclictestmaxvalue = 100"
        "dmesg", "list of strings, which should be in dmesg output", "[]", "dmesg = ['"OF: fdt: Machine model:'", '"gpio-193 (eeprom-wc): hogged as output/low'",]"
        "dmesg_false", "list of strings, which should be not in dmesg output", "[]", "dmesg = ['"crash'"]"
        "iperf", "list of dictionary for iperf test", "[]", 'iperf = [{"intervall":"1","minval":"290000000","cycles":"30"}]'
        "leds", "list of dictionary for checking leds", "[]", "leds = [{'"path'":'"/sys/class/leds/led-orange'", #bootval'":'"0'", '"onval'":'"1'},]"
        "lnx_commands", "list of dictionary for checking linux commands", "[]", "lnx_commands = [{'"cmd'":'"<your linux command'", '"val'":'"<string which is in output of command> or undef'"},]"
        "network_iperf_intervall", "iperf intervall", "1", "network_iperf_intervall = 1"
        "network_iperf_minval", "iperf minimum network throughput", "1", "network_iperf_minval = 9000000"
        "network_iperf_cylces", "iperf cycles", "1", "network_iperf_cycles = 30"
        "nvramdev", "nvram device", "6", "nvramdev = 6"
        "nvramcomp", "compatibility string of nvram device", "microchip,48l640", "nvramcomp = 'microchip,48l640'"
        "nvramsz", "size of nvram device", "8192", "nvramsz = 8192"
        "ping", "list of dict for ping config.", "[]", 'ping = [{"ip":"${default:serverip}","retry":"10"}]'
        "regdump", "list of dict for generic regdump", "[]", 'regdump = [{"address":"0x30340004"}, {"address":"0x30330070"}]'
        "rs485labdev", "path to device", "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_AB0PI210-if00-port0", 'rs485labdev = "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_AB0PI210-if00-port0"'
        "rs485baud", "baudrate used for test", "115200", 'rs485baud = "115200"'
        "rs485boarddev", "list of strings, each string contains a path to device which used in test", '["/dev/ttymxc2"]', 'rs485boarddev = ["/dev/ttymxc2"]'
        "rs485lengths", "list of strings. Each string is a length of data send over rs485 line", '["20", "100", "1024"]', 'rs485lengths = ["20", "100", "1024"]'
        "sensors", "list of dictionary for checking temperature sensors", "[]", "sensors = [{'path':''/sys/class/hwmon/hwmon0, "name":"tmp102", "tmpvalues":[{"valname" : "temp1_input", "min":"0", "max" : "100000" }]},]"
        "mtd_parts", "list of dictionary for MTD parts definition", "[]", "leds = [{'name':'SPL', 'size':'10000'},]"
        "ub_mtd_delete", "list of strings with MTD names which are allowed to delete", "[]", "ub_mtd_delete = ['SPL", "uboot"]"
        "ssh_keyfile"; "ssh setup: authentication using private key file ssh_keyfile", "None", "/home/{user}/.ssh/id_rsa"
        "ssh_password"; "ssh setup: set password for password ssh login", "None", "foobar"


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

argumentfiles
.............

it is convenient to collect tbot arguments in argumentsfile. As you
will have a lot of tbot arguments. We start in this example with
a base "argsBOARDNAME" file, which than other files include.

.. note::

    You can use shell variables also in argumentfiles!

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
bootcmd                  format bootcmd:<real bootcmd>, example bootcmd:net_nfs will execute "run net_nfs"
buildname                format buildname:<name of builder>, select the used buildhost.
labname                  format labname:<name of lab host>, select the used lab host (configure in tbot.ini with LABHOST_<name>] section)
gpiopower                use a gpio pin for boards power control
powershellscript         use a shellscript for boards power control
tinkerforge              use tinkerforge for boards power control
picocom                  use picocom for serial console
scriptcom                use a script for serial console
dfuutilloader            load SPL/U-Boot with dfu-util tool
uuuloader                load SPL/U-Boot with uuu tool from NXP
ignore_loglevel          add ignore_level to miscargs (deprecated, use set_ub_board_specific)
enterinitramfs           enter initramfs, add enterinitramfs to miscargs(deprecated, use set_ub_board_specific)
linux_no_cmd_after_login set nothing after linux login (beside disable clutter)
local                    enable if labhost and tbot host are the same (use SubprocessConnector)
noboardethinit           do no board ethinit in linux after login
nobootcon                set console to silent (deprecated, use set_ub_board_specific)
yoctobuild               use images from yoctobuild
ssh                      login to linux console through ssh (only possible if board already on and in linux)
do_power                 tbot handles boards power
always-on                board is already on, log into linux
rescue                   boot rescue system (deprecated, use flag bootcmd)
rescuetftp               boot rescue system, rescue image loaded through tftp (deprecated, use flag bootcmd)
emmc                     u-boot bootcmd "run boot_emmc" (deprecated, use flag bootcmd)
sdcard                   u-boot bootcmd "run boot_mmc" (deprecated, use flag bootcmd)
tftpfit                  u-boot bootcmd "run tftp_mmc" (deprecated, use flag bootcmd)
panic                    add death string "Kernel panic"
docker                   if you need to login to a docker container with proxyjump
uboot_no_env_set         do not set any U-Boot Environment after U-Boot login
set-ethconfig            setup ip config in U-Boot
useifconfig              use ifconfig for ip setup, else ip
poweroffonstart          if set, power off board before powering on
seggerloader             use segger debugger for breathing life into board
outside                  if lab host is only reachable with proxyjump
lablockid                pass lab lockid with lockid:<yourlockid>
======================== ====================================================
