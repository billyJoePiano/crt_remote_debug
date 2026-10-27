import subprocess, sys, site, importlib, os, shlex, psutil, signal
from pathlib import Path

from robot.libraries.BuiltIn import BuiltIn
from robot.libraries.Process import Process
from robot.api.deco import keyword, not_keyword
from typing import Literal



ROBOT_AUTO_KEYWORDS = False


_getStreamExceptions = set()
@not_keyword
def getOutStream():
    try:
        return sys.__stdout__.stream #type: ignore
    except Exception as e:
        e = str(e)
        if e not in _getStreamExceptions:
            _getStreamExceptions.add(e)
            print(e, file=sys.stderr)
        return None


@not_keyword
def getErrStream():
    try:
        return sys.__stderr__.stream #type: ignore
    except Exception as e:
        e = str(e)
        if e not in _getStreamExceptions:
            _getStreamExceptions.add(e)
            print(e, file=sys.stderr)
        return None


@not_keyword
def sp_run(*args, **kwargs):
    return subprocess.run(*args, stdout=getOutStream(), stderr=getErrStream(), **kwargs)


@not_keyword
def getVariable(varName: str):
    BuiltIn().variable_should_exist(f"\\${{{varName}}}")
    value = BuiltIn().get_variable_value(f"\\${{{varName}}}")
    if not (value and isinstance(value, str) and value.lower() != "none"):
        raise ValueError(f"Variable ${{{varName}}} is Falsey or not a string: {repr(value)}")
    return value


@not_keyword
def print2(*args, **kwargs):
    print(*args, file=getOutStream() or sys.stderr, **kwargs)


CRT_REMOTE_DEBUG_PKG_PATH = Path(__file__).resolve().parent

# old -- for Ubuntu 22.04.  10-26-2026, CRT recently upgraded to Ubuntu 26.04
# OPENSSH_SERVER_DEB_PKG_PATH = CRT_REMOTE_DEBUG_PKG_PATH / "openssh-server_8.9p1-3ubuntu0.17_amd64.deb"
# OPENSSH_SERVER_DEB_PKG_EXPECTED_CHECKSUM = "2baa4f236eebc486ec351ade604f1929286ede9ec3e2858a7206ddc412e3cbb6"

OPENSSH_CLIENT_DEB_PKG_PATH = CRT_REMOTE_DEBUG_PKG_PATH / "openssh-client_10.2p1-2ubuntu3.8_amd64v3.deb"
OPENSSH_SERVER_DEB_PKG_PATH = CRT_REMOTE_DEBUG_PKG_PATH / "openssh-server_10.2p1-2ubuntu3.8_amd64v3.deb"
OPENSSH_SERVER_DEB_PKG_EXPECTED_CHECKSUM = "d77954e865ba47c59d746e128ad649a81e82c3f648a49f4cbbf0a0a440867e17"
PINGGY_IO_SCRIPT_PATH = CRT_REMOTE_DEBUG_PKG_PATH / "pinggy_io.py"
PRIVATE_TUNNEL_SCRIPT_PATH = CRT_REMOTE_DEBUG_PKG_PATH / "private_tunnel.py"
TUNNEL_MONITOR_PID_FILE_PATH = CRT_REMOTE_DEBUG_PKG_PATH / "tunnel.pid"
HTTP_SERVER_PID_FILE_PATH = CRT_REMOTE_DEBUG_PKG_PATH / "httpd.pid"


HOSTNAME = subprocess.run(["hostname"], check=True, stdout=subprocess.PIPE, text=True).stdout.strip()
USER = subprocess.run(["whoami"], check=True, stdout=subprocess.PIPE, text=True).stdout.strip()
USER_AT_HOSTNAME = f"{USER}@{HOSTNAME}" # user fully-qualified name

USER_SSH_DIR_PATH = Path("~/.ssh").expanduser().resolve()
USER_SSH_DIR_PATH.mkdir(parents=True, exist_ok=True)
sp_run(["chmod", "700", str(USER_SSH_DIR_PATH)], check=True)

# binary paths (after installation)
USER_LOCAL_PATH = Path("~/.local").expanduser().resolve()
USER_LOCAL_PATH.mkdir(parents=True, exist_ok=True)
SSHD_PATH = USER_LOCAL_PATH / "usr/sbin/sshd"
SSHD_LIB_DIR_PATH = USER_LOCAL_PATH / "usr/lib/openssh"
SSH_CLIENT_PATH = USER_LOCAL_PATH / "usr/bin/ssh"

# ssh client configuration files
SSH_CLIENT_CONFIG_PATH = USER_SSH_DIR_PATH / "config"
SSH_CLIENT_KNOWN_HOSTS_PATH = USER_SSH_DIR_PATH / "known_hosts"

# sshd server configuration files
SSHD_CONFIG_PATH = USER_SSH_DIR_PATH / "sshd_config"
SSHD_AUTHORIZED_KEYS_PATH = USER_SSH_DIR_PATH / "authorized_keys"
SSHD_PID_PATH = USER_SSH_DIR_PATH / "sshd.pid"

# This key will be used by the sshd server, and can optionally also be used by ssh client as an identity (e.g. when connecting to private tunnel endpoints)
SSH_HOST_PRIV_KEY_PATH = USER_SSH_DIR_PATH / "ssh_host_key"
SSH_HOST_PUB_KEY_PATH = USER_SSH_DIR_PATH / "ssh_host_key.pub"


@keyword
def configure_ssh_host_key(privKey: str, pubKey: str):
    privKey = privKey.strip()
    pubKey = pubKey.strip()
    if not privKey or privKey.lower() == "none":
        if not pubKey or pubKey.lower() == "none":
            raise ValueError("Missing ${privKey} and ${pubKey} variable values")
        else:
            raise ValueError("Missing ${privKey} variable value")
    elif not pubKey or pubKey.lower() == "none":
        raise ValueError("Missing ${pubKey} variable value")

    SSH_HOST_PRIV_KEY_PATH.write_text(privKey + "\n")
    SSH_HOST_PUB_KEY_PATH.write_text(pubKey + "\n")
    sp_run(["chmod", "600", str(SSH_HOST_PRIV_KEY_PATH)], check=True)
    sp_run(["chmod", "644", str(SSH_HOST_PUB_KEY_PATH)], check=True)


_sshClientInstalled: bool = False
@keyword
def install_openssh_client():
    global _sshClientInstalled
    sp_run(["dpkg-deb", "-x", str(OPENSSH_CLIENT_DEB_PKG_PATH), str(USER_LOCAL_PATH)], check=True)
    _sshClientInstalled = True


@keyword
def configure_ssh_client(knownHosts: list[str]|str):
    SSH_CLIENT_CONFIG_PATH.write_text(f"""
IdentitiesOnly yes
ConnectTimeout 10
Host *
    UserKnownHostsFile {str(SSH_CLIENT_KNOWN_HOSTS_PATH)}
""")
    if isinstance(knownHosts, list):
        knownHosts = "\n".join(knownHosts)
    if knownHosts[-1] != "\n":
        knownHosts += "\n"
    SSH_CLIENT_KNOWN_HOSTS_PATH.write_text(knownHosts)


@keyword
def ssh_client_add_known_hosts(knownHosts: list[str]|str):
    if isinstance(knownHosts, list):
        knownHosts = "\n".join(knownHosts)
    if knownHosts[-1] != "\n":
        knownHosts += "\n"
    with SSH_CLIENT_KNOWN_HOSTS_PATH.open("a", encoding="utf-8") as f:
        f.write(knownHosts)


_sshdInstalled: bool = False
@keyword
def install_openssh_server():
    global _sshdInstalled
    checksumProc = subprocess.run(["sha256sum", str(OPENSSH_SERVER_DEB_PKG_PATH)], capture_output=True, text=True, check=True)
    expectedChecksum = f"{OPENSSH_SERVER_DEB_PKG_EXPECTED_CHECKSUM}  {str(OPENSSH_SERVER_DEB_PKG_PATH)}"
    if checksumProc.stdout.rstrip() != expectedChecksum or checksumProc.stderr:
        raise Exception(f"openssh-server debian package ({OPENSSH_SERVER_DEB_PKG_EXPECTED_CHECKSUM}) did not match expected checksum, or checksum process produced an unexpected stderr output\nExpected checksum: {expectedChecksum}\n  Actual checksum: {checksumProc.stdout.rstrip()}\nstderr output: {checksumProc.stderr}")
    else:
        print2(expectedChecksum)

    sp_run(["dpkg-deb", "-x", str(OPENSSH_SERVER_DEB_PKG_PATH), str(USER_LOCAL_PATH)], check=True)
    _sshdInstalled = True
    return str(SSHD_PATH)


@keyword
def install_openssh_server_if_needed():
    if not _sshdInstalled:
        return install_openssh_server()
    return str(SSHD_PATH)


@keyword
def configure_ssh_server(authorizedClientsPubKeys: list[str]|str, listenPort: int):
    if not _sshdInstalled:
        raise Exception("sshd not installed, call 'Install Openssh Server' keyword first")
    SSHD_CONFIG_PATH.write_text(f"""
Port {listenPort}
HostKey {str(SSH_HOST_PRIV_KEY_PATH)}
PidFile {str(SSHD_PID_PATH)}
AuthorizedKeysFile {str(SSHD_AUTHORIZED_KEYS_PATH)}
SshdSessionPath {str(SSHD_LIB_DIR_PATH)}/sshd-session
SshdAuthPath {str(SSHD_LIB_DIR_PATH)}/sshd-auth
StrictModes no
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
""")
    ssh_server_add_authorized_keys(authorizedClientsPubKeys)


@keyword
def ssh_server_add_authorized_keys(authorizedClientsPubKeys: list[str]|str, userFq: str = USER_AT_HOSTNAME) -> tuple[str, str]:
    if isinstance(authorizedClientsPubKeys, str):
        authorizedClientsPubKeys = authorizedClientsPubKeys.split("\n")
    fileContents = makeAuthorizedKeysContents(authorizedClientsPubKeys, userFq)
    with SSHD_AUTHORIZED_KEYS_PATH.open("a", encoding="utf-8") as f:
        f.write(fileContents)
    return str(SSHD_AUTHORIZED_KEYS_PATH), SSHD_AUTHORIZED_KEYS_PATH.read_text(encoding="utf-8")


@not_keyword
def makeAuthorizedKeysContents(authorizedClientsPubKeys: list[str], userFq: str = USER_AT_HOSTNAME):
    lines = []
    for pubKey in authorizedClientsPubKeys: #getVariable("sshAuthorizedClientsPubKeys").split("\n"):
        pubKey = pubKey.strip()
        if pubKey:
            pubKey += f" {userFq}"
        lines.append(pubKey)
    return "\n".join(lines) + "\n"


@keyword
def start_ssh_server(timeout: int|None = 60):
    if isinstance(timeout, str):
        if timeout.lower() == "none":
            timeout = None
        else:
            timeout = int(timeout)

    if not _sshdInstalled:
        raise Exception("sshd not installed, call 'Install Openssh Server' keyword first")

    print2(f"Starting ssh server daemon as {USER_AT_HOSTNAME}")
    sp_run([str(SSHD_PATH), "-f", str(SSHD_CONFIG_PATH), "-d"], check=True, timeout=timeout)
    print2("Successfully started ssh server daemon")


#TODO stop ssh server
#TODO when start_sshd runs, check whether sshd is already running using psutil (or is this neccessary? doesn't sshd check this itself based on the PID file?)



@keyword
def start_debugpy(addr="localhost", port=5678, in_process_debug_adapter: bool = False):
    try:
        import debugpy
    except ImportError:
        print2("Installing module debugpy")
        sp_run([sys.executable, "-m", "pip", "install", "debugpy"], check=True)
        importlib.reload(site)
        import debugpy

    debugpy.listen((addr, port), in_process_debug_adapter=in_process_debug_adapter)
    print2(f"debugpy listening on {addr}:{port}")
    debugpy.debug_this_thread()


@keyword
def is_tunnel_active() -> bool:
    return tunnelProcCheck()[0]


@not_keyword
def tunnelProcCheck() -> tuple[bool, int|None]:
    if not TUNNEL_MONITOR_PID_FILE_PATH.is_file():
        return False, None
    pid = TUNNEL_MONITOR_PID_FILE_PATH.read_text().strip()
    if not pid:
        return False, None
    try:
        pid = int(pid)
    except ValueError as e:
        raise ValueError(f"Invalid tunnel monitor process id: {repr(pid)} in {str(TUNNEL_MONITOR_PID_FILE_PATH)}")
    return psutil.pid_exists(pid), pid


@not_keyword
def httpdProcCheck() -> tuple[bool, int|None]:
    if not HTTP_SERVER_PID_FILE_PATH.is_file():
        return False, None
    pid = HTTP_SERVER_PID_FILE_PATH.read_text().strip()
    if not pid:
        return False, None
    try:
        pid = int(pid)
    except ValueError as e:
        raise ValueError(f"Invalid http file server process id: {repr(pid)} in {str(HTTP_SERVER_PID_FILE_PATH)}")
    return psutil.pid_exists(pid), pid


@keyword
def start_free_pinggy_io_tunnel_handler(*remotePortForwards):
    active, pid = tunnelProcCheck()
    if active:
        raise Exception(f"There is currently an active tunnel monitor process.  PID {pid}")
    cmdline = f"{shlex.quote(sys.executable)} -u {shlex.quote(str(PINGGY_IO_SCRIPT_PATH))} {shlex.join(remotePortForwards)} &\necho $! > {shlex.quote(str(TUNNEL_MONITOR_PID_FILE_PATH))}"
    print2(cmdline)
    os.system(cmdline)


@keyword
def start_private_tunnel_handler(remoteUser: str, remoteHost: str, remotePort: int):
    # NOTE: remote port forwards are hard-coded into private_tunnel.py
    # client identity will be the same private key used by sshd server
    remotePort = int(remotePort)

    active, pid = tunnelProcCheck()
    if active:
        raise Exception(f"There is currently an active tunnel monitor process.  PID {pid}")

    cmdline = f"{shlex.quote(sys.executable)} -u {shlex.quote(str(PRIVATE_TUNNEL_SCRIPT_PATH))} {shlex.join([f'{remoteUser}@{remoteHost}', str(remotePort)])} &\necho $! > {shlex.quote(str(TUNNEL_MONITOR_PID_FILE_PATH))}"
    print2(cmdline)
    os.system(cmdline)


@keyword
def stop_tunnel():
    active, pid = tunnelProcCheck()
    if not active or pid is None:
        if pid is None:
            raise Exception("There is no tunnel monitor process to stop")
        else:
            print2(f"Tunnel monitor process has already stopped, pid {pid}")
            TUNNEL_MONITOR_PID_FILE_PATH.unlink(missing_ok=True)
            return
    print2(f"Stopping tunnel, pid {pid}")
    os.kill(pid, signal.SIGTERM)
    for i in range(15):
        BuiltIn().sleep(1) #type:ignore
        active, pid = tunnelProcCheck()
        if not active or pid is None:
            TUNNEL_MONITOR_PID_FILE_PATH.unlink(missing_ok=True)
            return
    print2(f"Tunnel monitor process SIGTERM failed after 15+ second timeout, trying SIGKILL on pid {pid}")
    for i in range(15):
        os.kill(pid, signal.SIGKILL) #type:ignore
        BuiltIn().sleep(1) #type:ignore
        active, pid = tunnelProcCheck()
        if not active or pid is None:
            TUNNEL_MONITOR_PID_FILE_PATH.unlink(missing_ok=True)
            return
    raise Exception(f"Unable to stop pid {pid}")


@keyword
def start_http_file_server(port: int|None = None):
    if port is None:
        port = BuiltIn().get_variable_value(r"\${localHttpFileServerPort}", 8000) #type: ignore
    port = int(port) #type: ignore
    active, pid = httpdProcCheck()
    if active:
        raise Exception(f"There is currently an active http file server process.  PID {pid}")
    cmdline = f"{shlex.quote(sys.executable)} -u -m http.server -d / -b localhost {port} &\n\necho $! > {shlex.quote(str(HTTP_SERVER_PID_FILE_PATH))}"
    print2(cmdline)
    os.system(cmdline)


@keyword
def start_http_file_server_if_needed(port: int|None = None):
    if port is None:
        port = BuiltIn().get_variable_value(r"\${localHttpFileServerPort}", 8000) #type: ignore
    port = int(port) #type: ignore
    active, pid = httpdProcCheck()
    if active:
        print2(f"There is currently an active http file server process.  PID {pid}")
        return
    cmdline = f"{shlex.quote(sys.executable)} -u -m http.server -d / {port} &\n\necho $! > {shlex.quote(str(HTTP_SERVER_PID_FILE_PATH))}"
    print2(cmdline)
    os.system(cmdline)


@keyword
def stop_http_file_server():
    active, pid = httpdProcCheck()
    if not active or pid is None:
        if pid is None:
            raise Exception("There is no http file server process to stop")
        else:
            print2(f"Http file server process has already stopped, pid {pid}")
            HTTP_SERVER_PID_FILE_PATH.unlink(missing_ok=True)
            return
    print2(f"Stopping http file server, pid {pid}")
    os.kill(pid, signal.SIGTERM)
    for i in range(15):
        BuiltIn().sleep(1) #type:ignore
        active, pid = httpdProcCheck()
        if not active or pid is None:
            HTTP_SERVER_PID_FILE_PATH.unlink(missing_ok=True)
            return
    print2(f"Http file server process SIGTERM failed after 15+ second timeout, trying SIGKILL on pid {pid}")
    for i in range(15):
        os.kill(pid, signal.SIGKILL) #type:ignore
        BuiltIn().sleep(1) #type:ignore
        active, pid = httpdProcCheck()
        if not active or pid is None:
            HTTP_SERVER_PID_FILE_PATH.unlink(missing_ok=True)
            return
    raise Exception(f"Unable to stop pid {pid}")
