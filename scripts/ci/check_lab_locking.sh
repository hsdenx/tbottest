#!/bin/bash

tbotinifile="tbotconfig/foo/tbot.ini"
RET=0

echo "check lab locking mechansim"

echo "enable locking mechanism in ${tbotinifile}"
# save original tbot.ini
cp $tbotinifile $tbotinifile.save

# enable locking mechanism in tbot.ini
sed -i '/uselocking/c\uselocking = yes' $tbotinifile


echo "---- call without lockid, must fail ----"
tbottest/newtbot_starter.py @tbotconfig/foo/args/argsfoo-noeth tbotconfig.ci.testlab.uname > lab-lock-log
if [ "$?" != "1" ];then
	echo "Locking into Lab without passing lock id must fail"
	RET=1
fi
grep "NO LABLOCKID passed" lab-lock-log
if [ "$?" != "0" ];then
	echo "Locking into Lab without passing lock id must fail"
	RET=1
fi

echo "---- call with lockid foobar ----"
tbottest/newtbot_starter.py @tbotconfig/foo/args/argsfoo-noeth -f lablockid:foobar tbotconfig.ci.testlab.uname
if [ "$?" != "0" ];then
	echo "Locking into Lab with no lock must work"
	RET=1
fi

echo "---- call again with lockid foobar ----"
tbottest/newtbot_starter.py @tbotconfig/foo/args/argsfoo-noeth -f lablockid:foobar tbotconfig.ci.testlab.uname
if [ "$?" != "0" ];then
	echo "Locking into Lab with lock foobar must work"
	RET=1
fi

echo "---- call with wrong lockid must fail ----"
tbottest/newtbot_starter.py @tbotconfig/foo/args/argsfoo-noeth -f lablockid:foobar2 tbotconfig.ci.testlab.uname > lab-lock-log
if [ "$?" != "1" ];then
	echo "Locking into Lab with wrong lock foobar2 must fail"
	RET=1
fi

echo "---- Delete the lock with wrong lockid must fail ----"
tbottest/newtbot_starter.py @tbotconfig/foo/args/argsfoo-noeth -f lablockid:foobar tbottest.common.boardlocking.lab_rm_lock
if [ "$?" != "1" ];then
	echo "remove Locking with wrong lock foobar2 must fail"
	RET=1
fi
grep "passed lockid foobar2 is not the same as lockid" lab-lock-log
if [ "$?" != "0" ];then
	echo "remove Locking with wrong lock foobar2 must fail"
	RET=1
fi

echo "---- Delete lock with correct lockid must work ----"
tbottest/newtbot_starter.py @tbotconfig/foo/args/argsfoo-noeth -f lablockid:foobar tbottest.common.boardlocking.lab_rm_lock
if [ "$?" != "0" ];then
	echo "remove Locking with correct lock foobar must work"
	RET=1
fi

rm lab-lock-log
cp $tbotinifile.save $tbotinifile
exit $RET
