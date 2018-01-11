#!/usr/bin/env bash

DIR=`dirname $0`

function usage()
{
    echo "Shell script to handle vsphere signalfx client"
    echo ""
    echo "./test.sh"
    echo "\t-h --help"
    echo "\t--start"
    echo "\t--stop"
    echo ""
}

function get_pid()
{
    pid=$(ps -ef|grep "vsphere.py"|grep -v "grep"|awk '{print $2}')
    echo $pid
    return $pid
}

function status()
{
    pid=$(get_pid)
    if [ ! -z "$pid" ]
    then
        echo "Process running. PID : $pid"
    else
        echo "Process not running."
    fi
}

function start()
{
    pid=$(get_pid)
    if [ ! -z "$pid" ]
    then
        echo "Process already running. Will restart the process"
        kill -SIGUSR1 $pid
    fi
    echo "Starting the process"
    python3 "$DIR/vsphere.py" &
}

function stop()
{
    pid=$(get_pid)
    if [ ! -z "$pid" ]
    then
        echo "killing the process"
        kill -SIGUSR1 $pid
    else
        echo "No process is running"
    fi
}

while [ "$1" != "" ]; do
    PARAM=`echo $1 | awk -F= '{print $1}'`
    case $PARAM in
        -h | --help)
            usage
            exit
            ;;
        --start)
            start
            ;;
        --stop)
            stop
            ;;
        --status)
            status
            ;;
        *)
            echo "ERROR: unknown parameter \"$PARAM\""
            usage
            exit 1
            ;;
    esac
    shift
done