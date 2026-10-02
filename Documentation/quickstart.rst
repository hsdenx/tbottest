Quick Start
-----------

Please read also chapters :ref:`genericconfiguration` and :ref:`requirementslabhost`
and to get a rough overview for the lab setup check :ref:`labsetup`

To get fast a working setup you can use the script:

https://github.com/hsdenx/tbottest/tree/master/scripts/create_setup.sh

which will create you a complete base setup, as described in `configuration`_.

With ``--inter`` it asks for the console access and the power control of
the board and their settings. The generated ``tbot.ini`` holds only the
selected console and power control section, so tbot finds exactly one of
each. A unique prefix of a choice is enough (``tm`` for ``tm021``).
Without ``--inter`` it creates the setup the github CI uses: board
``foo``, picocom and sispmctrl.

Here an example run:

.. code-block:: bash

    $ wget -q https://github.com/hsdenx/tbottest/raw/master/scripts/create_setup.sh
    $ chmod 777 create_setup.sh
    $ ./create_setup.sh --inter
    Cloning into 'tbot'...
    [...]
    Cloning into 'tbottest'...
    [...]
    Check that ssh login without password works!
    Name of the lab: foolabname
    Hostname of the lab: 192.168.1.113
    Username for login into lab: pi
    Name of the board in your lab: foobar
    Vendor of the board (used in the aliases of setup.sh): foovendor
    Select console access for the board (picocom|kermit|scriptcom|telnet): picocom
    picocom baudrate: 115200
    picocom device: /dev/ttyUSB0
    picocom delay after exit: 3
    picocom noreset (True|False): True
    Select power switch method for the board (gpio|sispmctrl|shell|tinkerforge|tbox|tm021): sispmctrl
    Sispmctl MAC: 01:01:4f:09:5b
    Sispmctl Port: 1
    Created picocom console and sispmctrl powerctrl setup
    add commandline completions with:
    source tbottest/completions.sh

    add the aliases for starting tbot with:
    source setup.sh

    start tbot with the aliases from setup.sh:
    tbfoobar <testcase>

    Now edit lab config in tbotconfig/foobar/tbot.ini

    check that 'ssh pi@192.168.1.113' works without typing password
    than interactive lab should work:
    tbfoobarnoeth $conint.lab

    edit and adapt U-Boot settings in tbotconfig/foobar/foobar.ini and interactive U-Boot should work
    tbfoobarnoeth $conint.uboot

    edit linux settings in tbotconfig/foobar/foobar.ini and interactive Linux should work
    tbfoobarnoeth $conint.linux

    start CI tests with
    tbfoobarnoeth $con.ci.tests.all

Aliases for starting tbot
^^^^^^^^^^^^^^^^^^^^^^^^^

``create_setup.sh`` also writes ``setup.sh`` next to ``tbot``,
``tbottest`` and ``tbotconfig``, from the example
``tbottest/tbotconfig/setup.sh``, with the board name and the vendor
filled in. An existing ``setup.sh`` is left alone. Source it in that
directory:

.. code-block:: bash

    $ source setup.sh

For the example run above it defines:

.. csv-table::
        :header: "name", "what it is"

        "tb", "``tbottest/newtbot_starter.py``"
        "tbfoobar", "``tb`` with ``tbotconfig/foobar/args/argsfoobar``"
        "tbfoobarnoeth", "``tb`` with ``argsfoobar-noeth``, which adds ``-fnoethinit -fnoboardethinit``"
        "tbfoobarssh", "``tb`` with ``argsfoobar-noeth-ssh``, which adds ``-fnopoweroff -falways-on -fssh -fnouboot`` to that"
        "tbfoovendorfoobar, tbfoovendorfoobar-noeth, tbfoovendorfoobar-ssh", "the three above with ``-f boardname:foobar`` added"
        "$con, $conint, $tbtc", "the module paths ``tbotconfig``, ``tbotconfig.interactive``, ``tbottest.tc``"
        "$foobar", "the testcase module of the board, ``tbotconfig.tc_foobar``"

The commands the script prints at the end use these aliases.

The board name becomes a shell variable, so it must be a valid shell
variable name (no ``-``).

Test your new config and setup with:

.. code-block:: bash

    $ source setup.sh
    $ tbfoobarnoeth $conint.lab
    tbot starting ...
    ├─TBOT.FLAGS {'boardfile:tbotconfig/foobar/foobar.ini', 'noethinit', 'picocom', 'inifile:tbotconfig/foobar/tbot.ini', 'do_power', 'useifconfig'}
    ├─boardname now foobar
    ├─Using kas file kas-denx-withdldir.yml
    FILENAME  ~/temp/tbotconfig/foobar/tbot.ini-modified
    ├─Calling lab ...
    │   ├─[local] ssh -o BatchMode=yes -i /home/pi/.ssh/id_rsa -p 22 pi@192.168.1.113
    │   ├─Entering interactive shell ...
    │   ├─Press CTRL+] three times within 1 second to exit.

    foolabname: ~> exit
    │   ├─Exiting interactive shell ...
    │   └─Done. (3.496s)
    ├─────────────────────────────────────────
    └─SUCCESS (3.576s)
    $

To be independent of the installed tbot on the system, you can use the
tbot starter script:

https://github.com/hsdenx/tbottest/blob/master/newtbot_starter.py
