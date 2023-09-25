#!/bin/bash

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

SISPMCTRLMAC=01:01:4f:09:5b
SISPMCTRLPORT=1

PICOCOMBAUDRATE=115200
PICOCOMDEV=/dev/serial/by-id/usb-FTDI_C232HM-EDHSL-0_FT57MR3U-if00-port0
PICOCOMDELAY=3
PICOCOMNORESET=True

IPSETUPMASK=255.255.255.0
IPSETUPETH=00:30:D6:2C:A6:3D
IPSETUPIP=192.168.3.40
IPSETUPSERVERIP=192.168.3.1

if [ "$1" = "--inter" ]; then
	INTER=yes
fi

INTER=no
if [ "${INTER}" == "yes" ];then
	echo -n "Name of the lab: "
	read -r LABNAME
	echo -n "Hostname of the lab: "
	read -r LABHOSTNAME
	echo -n "Username for login into lab: "
	read -r LABUSER

	echo -n "Name of the board in your lab: "
	read -r BOARDNAME

	echo -n "Sispmctl MAC: "
	read -r SISPMCTLMAC

	echo -n "Sispmctl Port: "
	read -r SISPMCTLPORT
fi

## clone and create repos
git clone $tboturl tbot
git clone $tbottesturl tbottest

mkdir tbotconfig

cd tbottest
git checkout $tbottestbranch
git checkout -b "devel"
cd ..

cd tbot
git checkout $tbottag
git checkout -b "devel"
git am ../tbottest/patches/$tbottag/00*
cd ..

cd tbotconfig

cp ../tbottest/tbottest/tbotconfig/boardspecific.py .
cp ../tbottest/tbottest/tbotconfig/interactive.py .
# and only for github CI from interest
cp ../tbottest/tbottest/tbotconfig/ci.py .

mkdir $BOARDNAME
cd $BOARDNAME
mkdir args
cp ../../tbottest/tbottest/tbotconfig/BOARDNAME/args/args* args/

cp ../../tbottest/tbottest/tbotconfig/BOARDNAME/README.BOARDNAME README.$BOARDNAME
cp ../../tbottest/tbottest/tbotconfig/BOARDNAME/tbot.ini tbot.ini
cp ../../tbottest/tbottest/tbotconfig/BOARDNAME/BOARDNAME.ini $BOARDNAME.ini
cd ../..

# prepare some argumentfiles
sed -i "s|BOARDNAME|$BOARDNAME|g" ./tbotconfig/$BOARDNAME/args/argsbase

echo "@tbotconfig/${BOARDNAME}/args/argsbase" > ./tbotconfig/$BOARDNAME/args/args$BOARDNAME
echo "-f${TERMPROG}" >> ./tbotconfig/$BOARDNAME/args/args$BOARDNAME

echo "@tbotconfig/${BOARDNAME}/args/args$BOARDNAME" > ./tbotconfig/$BOARDNAME/args/args$BOARDNAME-noeth
echo "-fnoethinit" >> ./tbotconfig/$BOARDNAME/args/args$BOARDNAME-noeth

# replace BOARDNAME
sed -i "s|BOARDNAME|$BOARDNAME|g" ./tbotconfig/$BOARDNAME/tbot.ini

sed -i "/SET BOARDNAME to BOARDNAME/d" ./tbotconfig/boardspecific.py
sed -i "/!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!/d" ./tbotconfig/boardspecific.py
sed -i "/You use example implementation of boardspecific.py/d" ./tbotconfig/boardspecific.py
sed -i "/You really should use your own implementation/d" ./tbotconfig/boardspecific.py
sed -i "s|BOARDNAME_|$BOARDNAME\_|g" ./tbotconfig/boardspecific.py
sed -i "s|\"BOARDNAME\"|\"$BOARDNAME\"|g" ./tbotconfig/boardspecific.py
sed -i "s|\"BOARDNAME8g\"|\""$BOARDNAME"8g\"|g" ./tbotconfig/boardspecific.py


# insert LAB config in ./tbotconfig/$BOARDNAME/tbot.ini
sed -i "s|@@LABNAME@@|$LABNAME|g" ./tbotconfig/$BOARDNAME/tbot.ini
sed -i "s|@@LABHOSTNAME@@|$LABHOSTNAME|g" ./tbotconfig/$BOARDNAME/tbot.ini
sed -i "s|@@LABUSER@@|$LABUSER|g" ./tbotconfig/$BOARDNAME/tbot.ini

sed -i "s|@@SISPMCTRLMAC@@|$SISPMCTRLMAC|g" ./tbotconfig/$BOARDNAME/tbot.ini
sed -i "s|@@SISPMCTRLPORT@@|$SISPMCTRLPORT|g" ./tbotconfig/$BOARDNAME/tbot.ini

sed -i "s|@@PICOCOMBAUDRATE@@|$PICOCOMBAUDRATE|g" ./tbotconfig/$BOARDNAME/tbot.ini
sed -i "s|@@PICOCOMDEV@@|$PICOCOMDEV|g" ./tbotconfig/$BOARDNAME/tbot.ini
sed -i "s|@@PICOCOMDELAY@@|$PICOCOMDELAY|g" ./tbotconfig/$BOARDNAME/tbot.ini
sed -i "s|@@PICOCOMNORESET@@|$PICOCOMNORESET|g" ./tbotconfig/$BOARDNAME/tbot.ini

sed -i "s|@@IPSETUPMASK@@|$IPSETUPMASK|g" ./tbotconfig/$BOARDNAME/tbot.ini
sed -i "s|@@IPSETUPETH@@|$IPSETUPETH|g" ./tbotconfig/$BOARDNAME/tbot.ini
sed -i "s|@@IPSETUPIP@@|$IPSETUPIP|g" ./tbotconfig/$BOARDNAME/tbot.ini
sed -i "s|@@IPSETUPSERVERIP@@|$IPSETUPSERVERIP|g" ./tbotconfig/$BOARDNAME/tbot.ini

#sed -i "s|@@@@|$|g" ./tbotconfig/$BOARDNAME/tbot.ini


# end print some starter help
echo "add commandline completions with:
echo "source tbot/completions.sh"
echo "complete -F _newbot newtbot_starter.py"
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
