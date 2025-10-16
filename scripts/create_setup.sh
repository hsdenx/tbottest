#!/bin/bash

set -e

# tbot setup
tboturl=https://github.com/Rahix/tbot.git
tbottag="v0.10.6"

# tbottestsetup
tbottesturl=https://github.com/hsdenx/tbottest.git
tbottestbranch="master"

# tbotconfig setup
# default values, valid only for CI
BOARDNAME=foo
LABNAME=lab8
LABHOSTNAME=192.168.1.113
LABUSER=pi
TERMPROG=picocom
SELECTPOWERCTRL="none"

SCRIPTCOMSCRIPTNAME=./connect.sh
SCRIPTCOMEXITSTRING=~~.

PICOCOMBAUDRATE=115200
PICOCOMDEV=/dev/serial/by-id/usb-FTDI_C232HM-EDHSL-0_FT57MR3U-if00-port0
PICOCOMDELAY=3
PICOCOMNORESET=True

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

# $1 input_file
# $2 search_string
# $3 lines_to_delete
delete_line()
{
	input_file=$1
	search_string=$2
	lines_to_delete=$3
	temp_file=/tmp/initworktbot
	line_number=$(grep -n "$search_string" "$input_file" | cut -d: -f1)

	echo "delete line " $1 $2 $3
	echo "delete line " $line_number
	if [ -n "$line_number" ]; then
		# Use sed to delete the matched line and the next n lines
		sed -e "${line_number},$((line_number + lines_to_delete))d" "$input_file" > "$temp_file"

		# Replace the original file with the temporary file
		mv "$temp_file" "$input_file"

		#echo "Lines containing '$search_string' and the next $lines_to_delete lines deleted."
	else
		echo "Search string not found in the file."
	fi
}

# $1 path to tbot ini file
create_tbot_ini()
{
	filename=$1
	powerctrlstrings=("gpio" "sispmctrl" "shell" "tinkerforge")
	powerctrlstringall=""
	for substring in "${powerctrlstrings[@]}"; do
		powerctrlstringall+="$substring|"
	done
	FOUND="False"

	while [ "${FOUND}" == "False" ];do
		echo -n "Select power switch method for the board (${powerctrlstringall}) : "
		read -r SELECTPOWERCTRL
		for substring in "${powerctrlstrings[@]}"; do
			if [[ "${substring}" =~ "${SELECTPOWERCTRL}" ]]; then
				FOUND="True"
				SELECTPOWERCTRL="${substring}"
			fi
		done

		if [ "${FOUND}" == "False" ];then
			echo "Input ${SELECTPOWERCTRL} not supported, please enter one of ${powerctrlstringall}"
		fi
	done

	if [ ${SELECTPOWERCTRL} == "gpio" ]; then
		echo -n "gpio pin nr: "
		read -r VALUE
		sed -i "s|@@POWERGPIOPIN@@|$VALUE|g" $filename
		echo -n "gpio pin state: "
		read -r VALUE
		sed -i "s|@@POWERGPIOSTATE@@|$VALUE|g" $filename
	elif [ ${SELECTPOWERCTRL} == "shell" ]; then
		echo -n "shell name of shell script: "
		read -r VALUE
		sed -i "s|@@POWERSHELLSCRIPTNAME@@|$VALUE|g" $filename
	elif [ ${SELECTPOWERCTRL} == "sispmctrl" ]; then
		echo -n "Sispmctl MAC: "
		read -r VALUE
		sed -i "s|@@SISPMCTRLMAC@@|$VALUE|g" $filename
		echo -n "Sispmctl Port: "
		read -r VALUE
		sed -i "s|@@SISPMCTRLPORT@@|$VALUE|g" $filename
	elif [ ${SELECTPOWERCTRL} == "tinkerforge" ]; then
		echo -n "uid: "
		read -r VALUE
		sed -i "s|@@POWERTFUID@@|$VALUE|g" $filename
		echo -n "channel: "
		read -r VALUE
		sed -i "s|@@POWERTFCHANNEL@@|$VALUE|g" $filename
	fi

	for substring in "${powerctrlstrings[@]}"; do
		if [ ${SELECTPOWERCTRL} != $substring ]; then
			echo "Delete ${substring} example"
			if [[ ${substring} == "gpio" ]]; then
				delete_line $filename "GPIOPMCTRL_BOARDNAME" 2
			fi
			if [[ ${substring} == "shell" ]]; then
				delete_line $filename "POWERSHELLSCRIPT_BOARDNAME" 1
			fi
			if [[ ${substring} == "sispmctrl" ]]; then
				delete_line $filename "SISPMCTRL_BOARDNAME" 2
			fi
			if [[ ${substring} == "tinkerforge" ]]; then
				delete_line $filename "TF_BOARDNAME" 2
			fi
		fi
	done

	echo "Created ${SELECTPOWERCTRL} powerctrl setup"
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

		echo -n "Name of the lab: "
		read -r LABNAME
		echo -n "Hostname of the lab: "
		read -r LABHOSTNAME
		echo -n "Username for login into lab: "
		read -r LABUSER

		echo -n "Name of the board in your lab: "
		read -r BOARDNAME
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
		create_tbot_ini tbotconfig/$BOARDNAME/tbot.ini
	fi

	# prepare some argumentfiles
	sed -i "s|BOARDNAME|$BOARDNAME|g" ./tbotconfig/$BOARDNAME/args/argsbase

	echo "@tbotconfig/${BOARDNAME}/args/argsbase" > ./tbotconfig/$BOARDNAME/args/args$BOARDNAME
	echo "-f${TERMPROG}" >> ./tbotconfig/$BOARDNAME/args/args$BOARDNAME

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

	sed -i "s|@@SCRIPTCOMSCRIPTNAME@@|$SCRIPTCOMSCRIPTNAME|g" ./tbotconfig/$BOARDNAME/tbot.ini
	sed -i "s|@@SCRIPTCOMEXITSTRING@@|$SCRIPTCOMEXITSTRING|g" ./tbotconfig/$BOARDNAME/tbot.ini

	sed -i "s|@@PICOCOMBAUDRATE@@|$PICOCOMBAUDRATE|g" ./tbotconfig/$BOARDNAME/tbot.ini
	sed -i "s|@@PICOCOMDEV@@|$PICOCOMDEV|g" ./tbotconfig/$BOARDNAME/tbot.ini
	sed -i "s|@@PICOCOMDELAY@@|$PICOCOMDELAY|g" ./tbotconfig/$BOARDNAME/tbot.ini
	sed -i "s|@@PICOCOMNORESET@@|$PICOCOMNORESET|g" ./tbotconfig/$BOARDNAME/tbot.ini

	sed -i "s|@@IPSETUPMASK@@|$IPSETUPMASK|g" ./tbotconfig/$BOARDNAME/tbot.ini
	sed -i "s|@@IPSETUPETH@@|$IPSETUPETH|g" ./tbotconfig/$BOARDNAME/tbot.ini
	sed -i "s|@@IPSETUPIP@@|$IPSETUPIP|g" ./tbotconfig/$BOARDNAME/tbot.ini
	sed -i "s|@@IPSETUPSERVERIP@@|$IPSETUPSERVERIP|g" ./tbotconfig/$BOARDNAME/tbot.ini

	# for github CI we need sispmctl for board we use for testing
	sed -i "s|@@SISPMCTRLMAC@@|01:01:4f:09:5b|g" ./tbotconfig/$BOARDNAME/tbot.ini
	sed -i "s|@@SISPMCTRLPORT@@|1|g" ./tbotconfig/$BOARDNAME/tbot.ini
	delete_line ./tbotconfig/$BOARDNAME/tbot.ini "GPIOPMCTRL_$BOARDNAME" 2
	delete_line ./tbotconfig/$BOARDNAME/tbot.ini "POWERSHELLSCRIPT_$BOARDNAME" 1
	delete_line ./tbotconfig/$BOARDNAME/tbot.ini "TF_$BOARDNAME" 2

	#sed -i "s|@@@@|$|g" ./tbotconfig/$BOARDNAME/tbot.ini
fi

# end print some starter help
echo "add commandline completions with:
echo "source tbottest/completions.sh"
echo
echo "start tbot with:"
echo "tbottest/newtbot_starter.py @tbotconfig/$BOARDNAME/args/argsbase"
echo
echo "Now edit lab config in tbotconfig/$BOARDNAME/tbot.ini"
echo
echo "check that \'ssh ${LABUSER}@${LABHOSTNAME}\' works without typing password
echo "than interactive lab should work:"
echo "tbottest/newtbot_starter.py @tbotconfig/${BOARDNAME}/args/args${BOARDNAME}-noeth tbotconfig.interactive.lab"
echo
echo "edit and adapt U-Boot settings in tbotconfig/$BOARDNAME/${BOARDNAME}.ini and interactive U-Boot should work"
echo "tbottest/newtbot_starter.py @tbotconfig/${BOARDNAME}/args/args${BOARDNAME}-noeth tbotconfig.interactive.uboot"
echo
echo "edit linux settings in tbotconfig/$BOARDNAME/${BOARDNAME}.ini and interactive U-Boot should work"
echo "tbottest/newtbot_starter.py @tbotconfig/${BOARDNAME}/args/args${BOARDNAME}-noeth tbotconfig.interactive.linux"
echo
echo "start CI tests with"
echo "tbottest/newtbot_starter.py @tbotconfig/${BOARDNAME}/args/args${BOARDNAME}-noeth tbotconfig.ci.tests.all"
