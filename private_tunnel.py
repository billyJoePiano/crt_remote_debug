#!/usr/bin/env python3

import sys, subprocess, signal, shlex, time
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread, Event, RLock
from typing import Any


USER_SSH_DIR_PATH = Path("~/.ssh").expanduser().resolve()
SSH_HOST_PRIV_KEY_PATH = USER_SSH_DIR_PATH / "ssh_host_key"

HTTP_ALIVE_LISTENER_PORT = 9000
PORT_FORWARDS = ((2222, 2222), (5678, 5678), (8000, 8000), (HTTP_ALIVE_LISTENER_PORT, HTTP_ALIVE_LISTENER_PORT))
PORT_FORWARD_ARGS = tuple(f"-R{remote}:localhost:{local}" for remote, local in PORT_FORWARDS)

CMD_LINE = ("ssh", "-i", str(SSH_HOST_PRIV_KEY_PATH), *PORT_FORWARD_ARGS, sys.argv[1], "-p", sys.argv[2])

FLAG = Event()

tunnelProc: subprocess.Popen|None = None

def print2(*args, **kwargs):
    print(*args, flush=True, **kwargs)


def tunnel_monitor():
    global tunnelProc
    consecutiveFailures = 0
    while True:
        if tunnelProc is not None:
            raise Exception("private_tunnel.py tunnel_monitor(): tunnelProc variable was not None")
        FLAG.clear()
        print2(shlex.join(CMD_LINE))
        tunnelProc = subprocess.Popen(CMD_LINE)
        Thread(target=proc_init_check, args=[tunnelProc], daemon=True).start()
        success = False
        while True:
            flag = FLAG.wait(15)
            FLAG.clear()
            status = tunnelProc.poll()
            if status is not None:
                print2(f"private_tunnel.py tunnel_monitor(): SSH client process exited unexpectedly with exit code {status}")
                tunnelProc = None
                break
            elif flag:
                success = True
            else:
                print2("SSH tunnel seems to be dead... restarting")
                stop_tunnel()
                break
        if success:
            consecutiveFailures = 0
        else:
            consecutiveFailures += 1
            if consecutiveFailures > 2:
                print2("private_tunnel.py tunnel_monitor(): 3 or more consecutive failures to establish a tunnel.  Exiting private_tunnel.py")
                #signal.signal(signal.SIGTERM, signal.SIG_DFL) # remove signal handler.  not sure if this is neccessary to prevent duplicate exit messages?
                sys.exit(1)


def stop_tunnel():
    global tunnelProc
    if tunnelProc is None:
        raise Exception("private_tunnel.py stop_tunnel(): tunnelProc variable was None")
    tunnelProc.terminate()
    try:
        tunnelProc.wait(10)
    except TimeoutError:
        tunnelProc.kill()
    tunnelProc = None


def proc_init_check(tunnelProc: subprocess.Popen):
    try:
        tunnelProc.wait(30)
    except subprocess.TimeoutExpired as e:
        return #tunnelProc is still alive, exit
    FLAG.set() # tunnelProc died prematurely, notify tunnel_monitor on main thread


def end_process(signum, frame):
    print2(f"private_tunnel.py: Recieved signal {signum}. Shutting down tunnel processes...")
    if tunnelProc is not None:
        stop_tunnel()
        print2("private_tunnel.py: Exiting")
    else:
        print2("private_tunnel.py: No active tunnel process. Exiting")
    sys.exit(0)


def httpd():
    HTTPServer(('localhost', HTTP_ALIVE_LISTENER_PORT), HTTPHandler).serve_forever()


class HTTPHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        FLAG.set()
        self.send_response_only(200)
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        pass


if __name__ == "__main__":
    Thread(target=httpd, daemon=True).start()
    signal.signal(signal.SIGTERM, end_process)
    tunnel_monitor()
