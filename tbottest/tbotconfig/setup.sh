# Source this file in the directory that holds tbot, tbottest and
# tbotconfig to get short aliases for starting tbot:
#
#   source setup.sh
#
# create_setup.sh fills in the vendor and the name of the board.
PWD=$(pwd)
export TBOTCONFIGPATH=${PWD}
export TBOTARGSPATH=${TBOTCONFIGPATH}/tbotconfig/BOARDNAME/args
export TBOTTESTPATH=${PWD}/tbottest

export con=tbotconfig
export conint=$con.interactive
export tbtc=tbottest.tc
export BOARDNAME=$con.tc_BOARDNAME

alias tb=${TBOTTESTPATH}/newtbot_starter.py
alias tbBOARDNAME="tb @$TBOTARGSPATH/argsBOARDNAME"
alias tbBOARDNAMEnoeth="tb @$TBOTARGSPATH/argsBOARDNAME-noeth"
alias tbBOARDNAMEssh="tb @$TBOTARGSPATH/argsBOARDNAME-noeth-ssh"

alias tbVENDORBOARDNAME="tbBOARDNAME -f boardname:BOARDNAME"
alias tbVENDORBOARDNAME-noeth="tbBOARDNAMEnoeth -f boardname:BOARDNAME"
alias tbVENDORBOARDNAME-ssh="tbBOARDNAMEssh -f boardname:BOARDNAME"
