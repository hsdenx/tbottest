#!/bin/bash

set -e

# tbot setup
tboturl=https://github.com/Rahix/tbot.git
tbottag="v0.10.10"

# tbottestsetup
tbottesturl=https://github.com/hsdenx/tbottest.git
tbottestbranch="master"

# tbotconfig setup
# default values, valid only for CI
BOARDNAME=foo
VENDOR=vendor
LABNAME=lab8
LABHOSTNAME=192.168.1.113
LABUSER=pi
TERMPROG=picocom
SELECTPOWERCTRL=sispmctrl

SCRIPTCOMSCRIPTNAME=./connect.sh
SCRIPTCOMEXITSTRING=~~.

PICOCOMBAUDRATE=115200
PICOCOMDEV=/dev/serial/by-id/usb-FTDI_C232HM-EDHSL-0_FT57MR3U-if00-port0
PICOCOMDELAY=3
PICOCOMNORESET=True

KERMITCFGFILE=/home/pi/kermrc_BOARDNAME
KERMITDELAY=3

TELNETHOST=localhost
TELNETPORT=2013
TELNETDELAY=3

# for github CI we need sispmctl for board we use for testing
SISPMCTRLMAC=01:01:4f:09:5b
SISPMCTRLPORT=1

POWERGPIOPIN=17
POWERGPIOSTATE=1

POWERSHELLSCRIPTNAME=/tmp/power.sh

POWERTFUID=Nt2
POWERTFCHANNEL=1

TBOXPOWERPIN=P1_5V_EN

TM021DEVICE=/dev/relais
TM021BAUDRATE=500000
TM021TIMEOUT=5
TM021ADDRESS=0
TM021PORT=1
TM021DEBUG=False

IPSETUPMASK=255.255.255.0
IPSETUPETH=00:30:D6:2C:A6:3D
IPSETUPIP=192.168.3.40
IPSETUPSERVERIP=192.168.3.1

INTER=no

while [[ $# -gt 0 ]]
do
key="$1"

case $key in
    -i|--inter)
    shift # past argument
    INTER=yes
    ;;

    # checkout specific tbottest branch
    -b|--branch)
    shift # past argument
    tbottestbranch=$1
    shift # past argument
    ;;

    # checkout specific tbottest commitid
    -c|--commitid)
    shift # past argument
    tbottestbranch=$1
    shift # past argument
    ;;


    *)    # unknown option
    POSITIONAL+=("$1") # save it in an array may used later
    shift # past argument
    ;;
esac
done

# console and power control choices, and the tbot.ini section of each
consoles=("picocom" "kermit" "scriptcom" "telnet")
declare -A consolesection=(
	[picocom]=PICOCOM
	[kermit]=KERMIT
	[scriptcom]=SCRIPTCOM
	[telnet]=TELNET
)
powerctrls=("gpio" "sispmctrl" "shell" "tinkerforge" "tbox" "tm021")
declare -A powersection=(
	[gpio]=GPIOPMCTRL
	[sispmctrl]=SISPMCTRL
	[shell]=POWERSHELLSCRIPT
	[tinkerforge]=TF
	[tbox]=TBOX
	[tm021]=TM021
)

# $1 name of the variable to set
# $2 prompt
ask()
{
	echo -n "$2: "
	if ! read -r "$1"; then
		echo
		echo "No more input, giving up" >&2
		exit 1
	fi
}

# $1 prompt
# $2... the choices
# Sets SELECTED to the choice that equals the input, or to the only
# choice that starts with it.
select_one()
{
	local prompt=$1
	shift
	local choices=("$@")
	local choicestring
	choicestring=$(IFS="|"; echo "${choices[*]}")

	while true; do
		ask SELECTINPUT "${prompt} (${choicestring})"
		SELECTED=""
		local matches=0
		if [ -n "${SELECTINPUT}" ]; then
			for c in "${choices[@]}"; do
				if [ "${c}" == "${SELECTINPUT}" ]; then
					SELECTED="${c}"
					matches=1
					break
				fi
				if [[ "${c}" == "${SELECTINPUT}"* ]]; then
					SELECTED="${c}"
					matches=$((matches + 1))
				fi
			done
		fi
		if [ ${matches} -eq 1 ]; then
			return
		fi
		echo "Input ${SELECTINPUT} not supported, please enter one of ${choicestring}"
	done
}

# $1 ini file
# $2 section name
# Delete the section from its header up to and including the next empty
# line.
delete_section()
{
	awk -v hdr="[$2]" '
		$0 == hdr { skip = 1; next }
		skip && /^$/ { skip = 0; next }
		!skip { print }
	' "$1" > "$1.tmp"
	mv "$1.tmp" "$1"
}

# ask for the console and the power control of the board, and their
# settings
ask_tbot_ini()
{
	select_one "Select console access for the board" "${consoles[@]}"
	TERMPROG="${SELECTED}"

	if [ "${TERMPROG}" == "picocom" ]; then
		ask PICOCOMBAUDRATE "picocom baudrate"
		ask PICOCOMDEV "picocom device"
		ask PICOCOMDELAY "picocom delay after exit"
		ask PICOCOMNORESET "picocom noreset (True|False)"
	elif [ "${TERMPROG}" == "kermit" ]; then
		ask KERMITCFGFILE "kermit config file"
		ask KERMITDELAY "kermit delay after exit"
	elif [ "${TERMPROG}" == "scriptcom" ]; then
		ask SCRIPTCOMSCRIPTNAME "name of the console script"
		ask SCRIPTCOMEXITSTRING "string that exits the console script"
	elif [ "${TERMPROG}" == "telnet" ]; then
		ask TELNETHOST "telnet host"
		ask TELNETPORT "telnet port"
		ask TELNETDELAY "telnet delay after exit"
	fi

	select_one "Select power switch method for the board" "${powerctrls[@]}"
	SELECTPOWERCTRL="${SELECTED}"

	if [ "${SELECTPOWERCTRL}" == "gpio" ]; then
		ask POWERGPIOPIN "gpio pin nr"
		ask POWERGPIOSTATE "gpio pin state"
	elif [ "${SELECTPOWERCTRL}" == "shell" ]; then
		ask POWERSHELLSCRIPTNAME "shell name of shell script"
	elif [ "${SELECTPOWERCTRL}" == "sispmctrl" ]; then
		ask SISPMCTRLMAC "Sispmctl MAC"
		ask SISPMCTRLPORT "Sispmctl Port"
	elif [ "${SELECTPOWERCTRL}" == "tinkerforge" ]; then
		ask POWERTFUID "uid"
		ask POWERTFCHANNEL "channel"
	elif [ "${SELECTPOWERCTRL}" == "tbox" ]; then
		ask TBOXPOWERPIN "tbox power pin"
	elif [ "${SELECTPOWERCTRL}" == "tm021" ]; then
		ask TM021DEVICE "tm021 device"
		ask TM021BAUDRATE "tm021 baudrate"
		ask TM021TIMEOUT "tm021 timeout"
		ask TM021ADDRESS "tm021 relais address"
		ask TM021PORT "tm021 relais port"
		ask TM021DEBUG "tm021 debug (True|False)"
	fi
}

# $1 path to tbot ini file
# Fill in the console and power control settings, then drop the
# sections of the consoles and power controls not selected, so tbot
# finds exactly one of each.
fill_tbot_ini()
{
	filename=$1

	for v in SCRIPTCOMSCRIPTNAME SCRIPTCOMEXITSTRING \
		PICOCOMBAUDRATE PICOCOMDEV PICOCOMDELAY PICOCOMNORESET \
		KERMITCFGFILE KERMITDELAY \
		TELNETHOST TELNETPORT TELNETDELAY \
		POWERGPIOPIN POWERGPIOSTATE POWERSHELLSCRIPTNAME \
		SISPMCTRLMAC SISPMCTRLPORT POWERTFUID POWERTFCHANNEL \
		TBOXPOWERPIN \
		TM021DEVICE TM021BAUDRATE TM021TIMEOUT TM021ADDRESS TM021PORT TM021DEBUG; do
		sed -i "s|@@${v}@@|${!v}|g" "${filename}"
	done

	for c in "${consoles[@]}"; do
		if [ "${c}" != "${TERMPROG}" ]; then
			delete_section "${filename}" "${consolesection[$c]}_BOARDNAME"
		fi
	done
	for p in "${powerctrls[@]}"; do
		if [ "${p}" != "${SELECTPOWERCTRL}" ]; then
			delete_section "${filename}" "${powersection[$p]}_BOARDNAME"
		fi
	done
	# the xmodem example uses the device of the PICOCOM section
	if [ "${TERMPROG}" != "picocom" ]; then
		delete_section "${filename}" "XMODEM_CONFIG_BOARDNAME"
	fi

	echo "Created ${TERMPROG} console and ${SELECTPOWERCTRL} powerctrl setup"
}

## clone and create repos
TBOTEXISTS=no
if [ -d tbot ];then
	TBOTEXISTS=yes
	echo "Found existing tbot diretory, do nothing with it!"
	echo "Please check if it has the patches applied"
else
	git clone $tboturl tbot
fi

TBOTTESTEXISTS=no
if [ -d tbottest ];then
	TBOTTESTEXISTS=yes
	echo "Found existing tbottest diretory, do nothing with it!"
else
	git clone $tbottesturl tbottest
fi

TBOTCONFIGEXISTS=no
if [ -d tbotconfig ];then
	TBOTCONFIGEXISTS=yes
else
	mkdir tbotconfig
fi

if [ "$TBOTTESTEXISTS" == "no" ];then
	cd tbottest
	git checkout $tbottestbranch
	git checkout -b "devel"
	cd ..
fi

if [ "$TBOTEXISTS" == "no" ];then
	cd tbot
	git checkout $tbottag
	git checkout -b "devel"
	git am ../tbottest/patches/$tbottag/00*
	cd ..
fi

if [ "$TBOTCONFIGEXISTS" == "no" ];then
	cd tbotconfig

	cp ../tbottest/tbottest/tbotconfig/interactive.py .
	# and only for github CI from interest
	mkdir ci
	cp ../tbottest/tbottest/tbotconfig/ci/* ci

	if [ "${INTER}" == "yes" ];then
		echo "Check that ssh login without password works!"

		ask LABNAME "Name of the lab"
		ask LABHOSTNAME "Hostname of the lab"
		ask LABUSER "Username for login into lab"

		ask BOARDNAME "Name of the board in your lab"
		ask VENDOR "Vendor of the board (used in the aliases of setup.sh)"
	fi

	mkdir $BOARDNAME
	cd $BOARDNAME
	mkdir -p files/dumpfiles
	mkdir args
	cp ../../tbottest/tbottest/tbotconfig/BOARDNAME/args/args* args/

	cp ../../tbottest/tbottest/tbotconfig/BOARDNAME/README.BOARDNAME README.$BOARDNAME
	cp ../../tbottest/tbottest/tbotconfig/BOARDNAME/tbot.ini tbot.ini
	cp ../../tbottest/tbottest/tbotconfig/BOARDNAME/boardspecific.py boardspecific.py
	cp ../../tbottest/tbottest/tbotconfig/BOARDNAME/BOARDNAME.ini $BOARDNAME.ini
	cp ../../tbottest/tbottest/tbotconfig/BOARDNAME/BOARDNAME.py ../tc_$BOARDNAME.py
	sed -i "s|BOARDNAME|$BOARDNAME|g" ../tc_$BOARDNAME.py
	cd ../..

	if [ "${INTER}" == "yes" ];then
		ask_tbot_ini
	fi
	fill_tbot_ini tbotconfig/$BOARDNAME/tbot.ini

	# prepare some argumentfiles
	sed -i "s|BOARDNAME|$BOARDNAME|g" ./tbotconfig/$BOARDNAME/args/argsbase

	echo "@tbotconfig/${BOARDNAME}/args/argsbase" > ./tbotconfig/$BOARDNAME/args/args$BOARDNAME
	# kermit has no flag, tbot picks it from the KERMIT section
	if [ "${TERMPROG}" != "kermit" ]; then
		echo "-f${TERMPROG}" >> ./tbotconfig/$BOARDNAME/args/args$BOARDNAME
	fi

	echo "@tbotconfig/${BOARDNAME}/args/args$BOARDNAME" > ./tbotconfig/$BOARDNAME/args/args$BOARDNAME-noeth
	echo "-fnoethinit" >> ./tbotconfig/$BOARDNAME/args/args$BOARDNAME-noeth
	echo "-fnoboardethinit" >> ./tbotconfig/$BOARDNAME/args/args$BOARDNAME-noeth

	echo "@tbotconfig/${BOARDNAME}/args/args$BOARDNAME-noeth" > ./tbotconfig/$BOARDNAME/args/args$BOARDNAME-noeth-ssh
	echo "-fnopoweroff" >> ./tbotconfig/$BOARDNAME/args/args$BOARDNAME-noeth-ssh
	echo "-falways-on" >> ./tbotconfig/$BOARDNAME/args/args$BOARDNAME-noeth-ssh
	echo "-fssh" >> ./tbotconfig/$BOARDNAME/args/args$BOARDNAME-noeth-ssh
	echo "-fnouboot" >> ./tbotconfig/$BOARDNAME/args/args$BOARDNAME-noeth-ssh

	# replace BOARDNAME
	sed -i "s|BOARDNAME|$BOARDNAME|g" ./tbotconfig/$BOARDNAME/tbot.ini
	sed -i "s|BOARDNAME|$BOARDNAME|g" ./tbotconfig/$BOARDNAME/$BOARDNAME.ini

	sed -i "/SET BOARDNAME to BOARDNAME/d" ./tbotconfig/$BOARDNAME/boardspecific.py
	sed -i "/!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!/d" ./tbotconfig/$BOARDNAME/boardspecific.py
	sed -i "/You use example implementation of boardspecific.py/d" ./tbotconfig/$BOARDNAME/boardspecific.py
	sed -i "/You really should use your own implementation/d" ./tbotconfig/$BOARDNAME/boardspecific.py
	sed -i "s|BOARDNAME_|$BOARDNAME\_|g" ./tbotconfig/$BOARDNAME/boardspecific.py
	sed -i "s|\"BOARDNAME\"|\"$BOARDNAME\"|g" ./tbotconfig/$BOARDNAME/boardspecific.py
	sed -i "s|\"BOARDNAME8g\"|\""$BOARDNAME"8g\"|g" ./tbotconfig/$BOARDNAME/boardspecific.py

	# insert LAB config in ./tbotconfig/$BOARDNAME/tbot.ini
	sed -i "s|@@LABNAME@@|$LABNAME|g" ./tbotconfig/$BOARDNAME/tbot.ini
	sed -i "s|@@LABHOSTNAME@@|$LABHOSTNAME|g" ./tbotconfig/$BOARDNAME/tbot.ini
	sed -i "s|@@LABUSER@@|$LABUSER|g" ./tbotconfig/$BOARDNAME/tbot.ini

	sed -i "s|@@IPSETUPMASK@@|$IPSETUPMASK|g" ./tbotconfig/$BOARDNAME/tbot.ini
	sed -i "s|@@IPSETUPETH@@|$IPSETUPETH|g" ./tbotconfig/$BOARDNAME/tbot.ini
	sed -i "s|@@IPSETUPIP@@|$IPSETUPIP|g" ./tbotconfig/$BOARDNAME/tbot.ini
	sed -i "s|@@IPSETUPSERVERIP@@|$IPSETUPSERVERIP|g" ./tbotconfig/$BOARDNAME/tbot.ini

	#sed -i "s|@@@@|$|g" ./tbotconfig/$BOARDNAME/tbot.ini

	# aliases for starting tbot, see the quick start documentation
	if [ -e setup.sh ];then
		echo "Found existing setup.sh, do nothing with it!"
	else
		cp tbottest/tbottest/tbotconfig/setup.sh setup.sh
		sed -i "s|VENDOR|$VENDOR|g" setup.sh
		sed -i "s|BOARDNAME|$BOARDNAME|g" setup.sh
	fi
fi

# end print some starter help
echo "add commandline completions with:"
echo "source tbottest/completions.sh"
echo
echo "add the aliases for starting tbot with:"
echo "source setup.sh"
echo
echo "start tbot with the aliases from setup.sh:"
echo "tb${BOARDNAME} <testcase>"
echo
echo "Now edit lab config in tbotconfig/$BOARDNAME/tbot.ini"
echo
echo "check that 'ssh ${LABUSER}@${LABHOSTNAME}' works without typing password"
echo "than interactive lab should work:"
echo "tb${BOARDNAME}noeth \$conint.lab"
echo
echo "edit and adapt U-Boot settings in tbotconfig/$BOARDNAME/${BOARDNAME}.ini and interactive U-Boot should work"
echo "tb${BOARDNAME}noeth \$conint.uboot"
echo
echo "edit linux settings in tbotconfig/$BOARDNAME/${BOARDNAME}.ini and interactive Linux should work"
echo "tb${BOARDNAME}noeth \$conint.linux"
echo
echo "start CI tests with"
echo "tb${BOARDNAME}noeth \$con.ci.tests.all"
