#!/usr/bin/env python3
import re, io, subprocess, time, signal, sys
from threading import Thread, RLock, Event


tunnelProc: subprocess.Popen|None = None
tunnelStartTime: float|None = None

tunnelMonitorLock = RLock()
tunnelSuccess = Event()


def print2(*args, **kwargs):
    print(*args, flush=True, **kwargs)



def init(*remotePortForwards: str):
    with tunnelMonitorLock:
        if tunnelProc is not None:
            raise Exception("There is already a tunnel process running")
        print2("Starting free.pinggy.io tunnel...")
        proc = start_tunnel(*remotePortForwards)
    if not tunnelSuccess.wait(30):
        with tunnelMonitorLock:
            if tunnelProc is tunnelProc:
                stop_tunnel()
        raise Exception("Failure starting free.pinggy.io tunnel")
    tunnel_monitor(proc, *remotePortForwards)
        


def start_tunnel(*remotePortForwards):
    global tunnelProc, tunnelStartTime
    with tunnelMonitorLock:
        cmdline = ["ssh", "-p", "443"]
        for portForward in remotePortForwards:
            cmdline.append("-R")
            cmdline.append(portForward)
        cmdline.append("qr+tcp@free.pinggy.io")
        tunnelStartTime = time.monotonic()
        tunnelProc = subprocess.Popen(cmdline, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if tunnelProc.stdout:
            tunnelProc.stdout.close()
        tunnelSuccess.clear()
        Thread(target=pipe_reader, args=(tunnelProc,), daemon=True).start()
        return tunnelProc


def tunnel_monitor(proc, *remotePortForwards):
    retryCount = 0
    try:
        while True:
            with tunnelMonitorLock:
                if tunnelProc is not proc:
                    print2("pinggy_io.py tunnel_monitor: unexpected, tunnelProc has been replaced, exiting")
                    return

            proc.wait()
            endTime = time.monotonic()

            with tunnelMonitorLock:
                if tunnelProc is not proc: #signal from main thread that stop_tunnel() was run, so this thread should exit
                    return
                elif tunnelStartTime is None or endTime - tunnelStartTime < 60:
                    retryCount += 1
                    if retryCount < 3:
                        print2("pinggy_io.py tunnel_monitor: unexpected, tunnel run time was less than 60 seconds (or tunnelStartTime was reverted to None) ... retrying ...")
                    else:
                        print2("pinggy_io.py tunnel_monitor: unexpected, tunnel run time was less than 60 seconds (or tunnelStartTime was reverted to None) for 3 or more consecutive retries, exiting monitor loop")
                        return
                else:
                    print2("free.pinggy.io tunnel closed, re-opening...")
                    retryCount = 0
                
                proc = start_tunnel(*remotePortForwards)

            if not tunnelSuccess.wait(30):
                print2("pinggy_io.py tunnel_monitor: Failure starting free.pinggy.io tunnel, exiting")
                with tunnelMonitorLock:
                    if tunnelProc is proc:
                        stop_tunnel()
    except Exception as e:
        print2(f"pinggy_io.py tunnel_monitor: EXCEPTION: {e}")
        with tunnelMonitorLock:
            if tunnelProc is proc:
                stop_tunnel()


def stop_tunnel():
    global tunnelProc, tunnelProc, tunnelStartTime
    with tunnelMonitorLock:
        if tunnelProc is None:
            raise Exception("There is no tunnel process to stop")
        print2("Stopping tunnel process...")
        tunnelProc.terminate()
        try:
            tunnelProc.wait(10)
        except TimeoutError:
            tunnelProc.kill()
        tunnelProc = None
        tunnelStartTime = None


def pipe_reader(proc: subprocess.Popen):
    if not proc.stdout:
        print2("pinggy_io.py pipe_reader: unexpected, no stdout on proccess, exiting")
        return
    try:
        FILTER_REGEX = re.compile(r"^\s?(RB: \d+, SB: \d+, TC: \d+, AC: \d+\s*)+$")
        EXCLUDE_STRS = ("Pseudo-terminal will not be allocated because stdin is not a terminal.", "You are not authenticated.")
        for line in iter(proc.stdout.readline, ""):
            if FILTER_REGEX.match(line):
                continue
            if len(line) > 0 and line[-1] == "\n":
                lineCleaned = line[:-1]
                if len(lineCleaned) > 0 and lineCleaned[-1] == "\r":
                    lineCleaned = lineCleaned[:-1]
            else:
                lineCleaned = line
            if lineCleaned in EXCLUDE_STRS:
                continue
            print2(line, end="")
            if lineCleaned[:6] == "tcp://" and "pinggy-free.link" in line:
                with tunnelMonitorLock:
                    if tunnelProc is tunnelProc:
                        tunnelSuccess.set()
                    else:
                        print2("pinggy_io.py pipe_reader: unexpected, tunnelProc has been replaced, exiting")
                        break
    except Exception as e:
        print2(f"pinggy_io.py pipe_reader: EXCEPTION: {e}")
    finally:
        proc.stdout.close()


def end_process(signum, frame):
    stop_tunnel()


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, end_process)
    init(*sys.argv[1:])
