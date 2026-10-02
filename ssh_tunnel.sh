#!/bin/bash

SSH_PID=0
FINISHED_CLEANUP=No

function cleanup() {
    if [ $FINISHED_CLEANUP == "Yes" ]
    then
        exit 0
    fi

    echo "Tearing down SSH tunnel..."
    if ! kill -0 $SSH_PID 2> /dev/null
    then
        FINISHED_CLEANUP=Yes
        exit 0
    fi
    kill $SSH_PID
    for i in {1..5}
    do
        sleep 1
        if ! kill -0 $SSH_PID 2> /dev/null
        then
            FINISHED_CLEANUP=Yes
            exit 0
        fi
    done
    echo "kill SSH_PID didn't work ... using kill -9"
    kill -9 $SSH_PID
    FINISHED_CLEANUP=Yes
    exit 0
}

trap cleanup EXIT SIGINT SIGTERM SIGHUP

while true
do
    TZ="America/New_York" date +"%r %Z"
    ssh -p 443 -R0:localhost:2222 qr+tcp@free.pinggy.io &
    SSH_PID=$!
    wait $SSH_PID
done
