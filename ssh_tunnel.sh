#!/bin/bash

PID_FILE=$1

SSH_PID=0
FINISHED_CLEANUP=No

function start_tunnel() {
    ssh -p 443 -R0:localhost:2222 qr+tcp@free.pinggy.io 2>&1 &
    SSH_PID=$!
    echo -n $SSH_PID > $PID_FILE
    wait $SSH_PID
}

function cleanup() {
    if [ $FINISHED_CLEANUP == "Yes" ]
    then
        exit 0
    fi

    echo "ssh_tunnel.sh: Tearing down SSH tunnel..."
    kill_proc $SSH_PID SSH_PID
    FINISHED_CLEANUP=Yes
    exit 0
}

function kill_proc() {
    if ! kill -0 $1 2> /dev/null
    then
        return 0
    fi
    kill $1
    for i in {1..5}
    do
        sleep 1
        if ! kill -0 $1 2> /dev/null
        then
            FINISHED_CLEANUP=Yes
            return 0
        fi
    done
    echo "kill $2 didn't work ... using kill -9"
    kill -9 $1
}

trap cleanup EXIT SIGINT SIGTERM SIGHUP

while true
do
    TZ="America/New_York" date +"%r %Z"
    start_tunnel

    if ! PID_FILE_CONTENTS=$(cat "$PID_FILE" 2> /dev/null)
    then
        exit 0
    elif [ "$PID_FILE_CONTENTS" != "$SSH_PID" ]
    then
        exit 0
    fi

    echo "SSH tunnel closed, re-opening..."
done
