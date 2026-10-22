#!/bin/bash

set -e

# The script may update the tbottest clone it lives in. Run it from a copy,
# so bash does not read a file that changes under it.
if [ -z "${CREATE_SETUP_COPY}" ]; then
	CREATE_SETUP_COPY=$(mktemp)
	cp "$0" "${CREATE_SETUP_COPY}"
	export CREATE_SETUP_COPY
	exec bash "${CREATE_SETUP_COPY}" "$@"
fi
trap 'rm -f "${CREATE_SETUP_COPY}"' EXIT

# tbot setup: tbot with the patches tbottest needs, as a branch of its own;
# TBOT_URL and TBOT_BRANCH in the environment override it (mirrors, tests)
tboturl=${TBOT_URL:-https://github.com/EmbLux-Kft/tbot.git}
tbotbranch=${TBOT_BRANCH:-v0.10.10-emb}

# tbottestsetup; TBOTTEST_URL in the environment overrides the url
tbottesturl=${TBOTTEST_URL:-https://github.com/hsdenx/tbottest.git}
tbottestbranch="master"
# set with -c: tbottest stays on this commit and is not updated
tbottestcommit=""

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

TBOXHWDAEMONBOARDNAME=dut0

SHELLYDEVICE=192.168.1.86
SHELLYID=0

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
# --ci: also copy the testcases the github CI of tbottest runs
CISETUP=no
# --no-update: leave existing tbot and tbottest clones as they are
UPDATE=yes
# --json: the configuration as tbot.json and <board>.json, without
# boardspecific.py, instead of tbot.ini, <board>.ini and boardspecific.py
CFGEXT=ini

while [[ $# -gt 0 ]]
do
key="$1"

case $key in
    -i|--inter)
    shift # past argument
    INTER=yes
    ;;

    # copy tbotconfig/ci, only needed for the github CI of tbottest
    --ci)
    shift # past argument
    CISETUP=yes
    ;;

    # do not bring existing tbot and tbottest clones up to date
    --no-update)
    shift # past argument
    UPDATE=no
    ;;

    # configuration in JSON files instead of ini files
    --json)
    shift # past argument
    CFGEXT=json
    ;;

    # checkout specific tbottest branch
    -b|--branch)
    shift # past argument
    tbottestbranch=$1
    shift # past argument
    ;;

    # checkout specific tbottest commitid; the clone is not updated then
    -c|--commitid)
    shift # past argument
    tbottestcommit=$1
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
powerctrls=("gpio" "sispmctrl" "shell" "shelly" "tinkerforge" "tbox" "tbox-hwdaemon" "tm021")
declare -A powersection=(
	[gpio]=GPIOPMCTRL
	[sispmctrl]=SISPMCTRL
	[shell]=POWERSHELLSCRIPT
	[shelly]=SHELLY
	[tinkerforge]=TF
	[tbox]=TBOX
	[tbox-hwdaemon]=TBOX_HWDAEMON
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
# the value $1 as sed replacement for a placeholder; in a JSON file it
# lands in a string, so " and \ get a backslash
cfgval()
{
	local v="$1"
	if [ "${CFGEXT}" == "json" ]; then
		v="${v//\\/\\\\\\\\}"
		v="${v//\"/\\\\\"}"
	fi
	printf '%s' "${v}"
}

delete_section()
{
	if [ "${1##*.}" == "json" ]; then
		python3 - "$1" "$2" <<'EOF'
import json
import sys

path, section = sys.argv[1:]
with open(path) as f:
    data = json.load(f)
data.pop(section, None)
with open(path, "w") as f:
    json.dump(data, f, indent=4)
    f.write("\n")
EOF
		return
	fi
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
	elif [ "${SELECTPOWERCTRL}" == "shelly" ]; then
		ask SHELLYDEVICE "Shelly device (IP, MAC or mDNS name)"
		ask SHELLYID "Shelly channel"
	elif [ "${SELECTPOWERCTRL}" == "sispmctrl" ]; then
		ask SISPMCTRLMAC "Sispmctl MAC"
		ask SISPMCTRLPORT "Sispmctl Port"
	elif [ "${SELECTPOWERCTRL}" == "tinkerforge" ]; then
		ask POWERTFUID "uid"
		ask POWERTFCHANNEL "channel"
	elif [ "${SELECTPOWERCTRL}" == "tbox" ]; then
		ask TBOXPOWERPIN "tbox power pin"
	elif [ "${SELECTPOWERCTRL}" == "tbox-hwdaemon" ]; then
		ask TBOXHWDAEMONBOARDNAME "hwdamon DUT name or slot number"
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
		TBOXPOWERPIN TBOXHWDAEMONBOARDNAME SHELLYDEVICE SHELLYID \
		TM021DEVICE TM021BAUDRATE TM021TIMEOUT TM021ADDRESS TM021PORT TM021DEBUG; do
		sed -i "s|@@${v}@@|$(cfgval "${!v}")|g" "${filename}"
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

# $1 directory of an existing clone
# $2 url
# $3 branch
# Bring the clone to the state of the branch at the url: nothing to do if it
# is there already, a fast forward if the clone has neither commits of its
# own nor local changes. Otherwise only say why not, no local work is lost.
update_repo()
{
	local dir=$1 url=$2 branch=$3 head new

	if ! git -C "${dir}" rev-parse --git-dir > /dev/null 2>&1; then
		echo "${dir}: not a git repository, not updated"
		return 0
	fi
	if ! git -C "${dir}" fetch -q "${url}" "${branch}"; then
		echo "${dir}: fetching ${branch} from ${url} failed, not updated" >&2
		return 0
	fi
	head=$(git -C "${dir}" rev-parse HEAD)
	new=$(git -C "${dir}" rev-parse FETCH_HEAD)
	if [ "${head}" == "${new}" ]; then
		echo "${dir}: up to date with ${branch} of ${url}"
	elif ! git -C "${dir}" merge-base --is-ancestor HEAD FETCH_HEAD; then
		echo "${dir}: has commits not in ${branch} of ${url}, not updated" >&2
	elif [ -n "$(git -C "${dir}" status --porcelain --untracked-files=no)" ]; then
		echo "${dir}: has local changes, not updated" >&2
	else
		git -C "${dir}" merge -q --ff-only FETCH_HEAD
		echo "${dir}: updated to ${branch} of ${url} ($(git -C "${dir}" rev-parse --short HEAD))"
	fi
}

## clone and create repos
TBOTEXISTS=no
if [ -d tbot ];then
	TBOTEXISTS=yes
	if [ "${UPDATE}" == "yes" ];then
		update_repo tbot "${tboturl}" "${tbotbranch}"
	else
		echo "Found existing tbot directory, not updated (--no-update)"
	fi
else
	git clone -b "${tbotbranch}" "${tboturl}" tbot
fi

TBOTTESTEXISTS=no
if [ -d tbottest ];then
	TBOTTESTEXISTS=yes
	if [ -n "${tbottestcommit}" ];then
		echo "Found existing tbottest directory, not updated (-c ${tbottestcommit})"
	elif [ "${UPDATE}" == "yes" ];then
		update_repo tbottest "${tbottesturl}" "${tbottestbranch}"
	else
		echo "Found existing tbottest directory, not updated (--no-update)"
	fi
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
	git checkout ${tbottestcommit:-$tbottestbranch}
	git checkout -b "devel"
	cd ..
fi

if [ "$TBOTCONFIGEXISTS" == "no" ];then
	cd tbotconfig

	# tbotconfig must be a regular package, the board modules are
	# imported as tbotconfig.<board>.boardspecific
	cp ../tbottest/tbottest/tbotconfig/__init__.py .
	cp ../tbottest/tbottest/tbotconfig/interactive.py .
	# only for the github CI of tbottest
	if [ "${CISETUP}" == "yes" ];then
		mkdir ci
		cp ../tbottest/tbottest/tbotconfig/ci/* ci
	fi

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
	# ini or json, never both; boardspecific.py only with ini
	cp ../../tbottest/tbottest/tbotconfig/BOARDNAME/tbot.${CFGEXT} tbot.${CFGEXT}
	cp ../../tbottest/tbottest/tbotconfig/BOARDNAME/BOARDNAME.${CFGEXT} $BOARDNAME.${CFGEXT}
	if [ "${CFGEXT}" == "ini" ]; then
		cp ../../tbottest/tbottest/tbotconfig/BOARDNAME/boardspecific.py boardspecific.py
	fi
	cp ../../tbottest/tbottest/tbotconfig/BOARDNAME/BOARDNAME.py ../tc_$BOARDNAME.py
	sed -i "s|BOARDNAME|$BOARDNAME|g" ../tc_$BOARDNAME.py
	cd ../..

	if [ "${INTER}" == "yes" ];then
		ask_tbot_ini
	fi
	fill_tbot_ini tbotconfig/$BOARDNAME/tbot.${CFGEXT}

	# prepare some argumentfiles
	sed -i "s|BOARDNAME|$BOARDNAME|g" ./tbotconfig/$BOARDNAME/args/argsbase
	if [ "${CFGEXT}" == "json" ]; then
		sed -i "s|/tbot.ini$|/tbot.json|; s|/${BOARDNAME}.ini$|/${BOARDNAME}.json|" \
			./tbotconfig/$BOARDNAME/args/argsbase
	fi

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
	sed -i "s|BOARDNAME|$BOARDNAME|g" ./tbotconfig/$BOARDNAME/tbot.${CFGEXT}
	sed -i "s|BOARDNAME|$BOARDNAME|g" ./tbotconfig/$BOARDNAME/$BOARDNAME.${CFGEXT}

	if [ "${CFGEXT}" == "ini" ]; then
		sed -i "/SET BOARDNAME to BOARDNAME/d" ./tbotconfig/$BOARDNAME/boardspecific.py
		sed -i "/!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!/d" ./tbotconfig/$BOARDNAME/boardspecific.py
		sed -i "/You use example implementation of boardspecific.py/d" ./tbotconfig/$BOARDNAME/boardspecific.py
		sed -i "/You really should use your own implementation/d" ./tbotconfig/$BOARDNAME/boardspecific.py
		sed -i "s|BOARDNAME_|$BOARDNAME\_|g" ./tbotconfig/$BOARDNAME/boardspecific.py
		sed -i "s|\"BOARDNAME\"|\"$BOARDNAME\"|g" ./tbotconfig/$BOARDNAME/boardspecific.py
		sed -i "s|\"BOARDNAME8g\"|\""$BOARDNAME"8g\"|g" ./tbotconfig/$BOARDNAME/boardspecific.py
	fi

	# insert LAB config in ./tbotconfig/$BOARDNAME/tbot.ini or tbot.json
	sed -i "s|@@LABNAME@@|$(cfgval "$LABNAME")|g" ./tbotconfig/$BOARDNAME/tbot.${CFGEXT}
	sed -i "s|@@LABHOSTNAME@@|$(cfgval "$LABHOSTNAME")|g" ./tbotconfig/$BOARDNAME/tbot.${CFGEXT}
	sed -i "s|@@LABUSER@@|$(cfgval "$LABUSER")|g" ./tbotconfig/$BOARDNAME/tbot.${CFGEXT}

	sed -i "s|@@IPSETUPMASK@@|$(cfgval "$IPSETUPMASK")|g" ./tbotconfig/$BOARDNAME/tbot.${CFGEXT}
	sed -i "s|@@IPSETUPETH@@|$(cfgval "$IPSETUPETH")|g" ./tbotconfig/$BOARDNAME/tbot.${CFGEXT}
	sed -i "s|@@IPSETUPIP@@|$(cfgval "$IPSETUPIP")|g" ./tbotconfig/$BOARDNAME/tbot.${CFGEXT}
	sed -i "s|@@IPSETUPSERVERIP@@|$(cfgval "$IPSETUPSERVERIP")|g" ./tbotconfig/$BOARDNAME/tbot.${CFGEXT}

	# aliases for starting tbot, see the quick start documentation
	if [ -e setup.sh ];then
		if grep -q "^alias tb${BOARDNAME}=" setup.sh; then
			echo "Found existing setup.sh, do nothing with it!"
		else
			# left alone as well, but the aliases printed below are missing
			echo "WARNING: the existing setup.sh has no aliases for ${BOARDNAME}, it is left as it is."
			echo "Write a setup.sh for ${BOARDNAME} with:"
			echo "cp tbottest/tbottest/tbotconfig/setup.sh setup.sh"
			echo "sed -i \"s|VENDOR|${VENDOR}|g; s|BOARDNAME|${BOARDNAME}|g\" setup.sh"
		fi
	else
		cp tbottest/tbottest/tbotconfig/setup.sh setup.sh
		sed -i "s|VENDOR|$VENDOR|g" setup.sh
		sed -i "s|BOARDNAME|$BOARDNAME|g" setup.sh
	fi
fi

# for a git repository of the setup: tbot and tbottest are clones of their
# own; the template has no leading dot, so it does not apply to tbottest
if [ ! -e .gitignore ];then
	cp tbottest/tbottest/tbotconfig/gitignore .gitignore
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
echo "Now edit lab config in tbotconfig/$BOARDNAME/tbot.${CFGEXT}"
echo
echo "check that 'ssh ${LABUSER}@${LABHOSTNAME}' works without typing password"
echo "than interactive lab should work:"
echo "tb${BOARDNAME}noeth \$conint.lab"
echo
echo "edit and adapt U-Boot settings in tbotconfig/$BOARDNAME/${BOARDNAME}.${CFGEXT} and interactive U-Boot should work"
echo "tb${BOARDNAME}noeth \$conint.uboot"
echo
echo "edit linux settings in tbotconfig/$BOARDNAME/${BOARDNAME}.${CFGEXT} and interactive Linux should work"
echo "tb${BOARDNAME}noeth \$conint.linux"
echo
if [ "${CISETUP}" == "yes" ];then
	echo "start CI tests with"
	echo "tb${BOARDNAME}noeth \$con.ci.tests.all"
fi
