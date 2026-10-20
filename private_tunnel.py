#!/usr/bin/env python3

import sys, subprocess, signal
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread, Event, RLock


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
    while True:
        if tunnelProc is not None:
            raise Exception("private_tunnel.py tunnel_monitor(): tunnelProc variable was not None")
        FLAG.clear()
        tunnelProc = subprocess.Popen(CMD_LINE)
        Thread(target=proc_init_check, args=[tunnelProc], daemon=True).start()
        while True:
            flag = FLAG.wait(15)
            FLAG.clear()
            status = tunnelProc.poll()
            if status is not None:
                print2(f"SSH client process exited unexpectedly with exit code {status}.  Shutting down private_tunnel.py")
                tunnelProc = None
                sys.exit(1)
            elif not flag:
                print2("SSH tunnel seems to be dead... restarting")
                stop_tunnel()
                break


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
    if tunnelProc is None:
        return
    print2(f"private_tunnel.py: Recieved signal {signum}. Shutting down tunnel processes...")
    stop_tunnel()
    sys.exit(0)


def httpd():
    HTTPServer(('localhost', HTTP_ALIVE_LISTENER_PORT), HTTPHandler).serve_forever()


class HTTPHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        FLAG.set()
        self.send_response_only(200)
        self.end_headers()


if __name__ == "__main__":
    Thread(target=httpd, daemon=True).start()
    tunnel_monitor()
