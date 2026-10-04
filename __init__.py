import subprocess, sys, os, shlex, psutil
from pathlib import Path

from robot.libraries.BuiltIn import BuiltIn
from robot.api.deco import keyword, not_keyword


ROBOT_AUTO_KEYWORDS = False


_getStreamExceptions = set()
@not_keyword
def getStream():
    try:
        return sys.__stdout__.stream
    except Exception as e:
        e = str(e)
        if e not in _getStreamExceptions:
            _getStreamExceptions.add(e)
            print2(e)
        return None


@not_keyword
def sp_run(*args, **kwargs):
    stderrStream = getStream()
    return subprocess.run(*args, stdout=stderrStream, **kwargs) if stderrStream else subprocess.run(*args, **kwargs)


@not_keyword
def getVariable(varName: str):
    BuiltIn().variable_should_exist(f"\\${{{varName}}}")
    value = BuiltIn().get_variable_value(f"\\${{{varName}}}")
    if not (value and isinstance(value, str) and value.lower() != "none"):
        raise ValueError(f"Variable ${{{varName}}} is Falsey or not a string: {repr(value)}")
    return value


@not_keyword
def print2(*args):
    print(*args, file=sys.stderr)



hostname = subprocess.run(["hostname"], check=True, stdout=subprocess.PIPE, text=True).stdout.strip()
user = subprocess.run(["whoami"], check=True, stdout=subprocess.PIPE, text=True).stdout.strip()
userFq = f"{user}@{hostname}" # user fully-qualified name

sshDir = Path("~/.ssh").expanduser().resolve()
sshDir.mkdir(parents=True, exist_ok=True)
sp_run(["chmod", "700", str(sshDir)], check=True)

authorizedKeysFile = sshDir / "authorized_keys"
@not_keyword
def getAuthorizedKeys(userFq: str = userFq):
    lines = []
    for line in getVariable("sshAuthorizedClientsPubKeys").split("\n"):
        line = line.strip()
        if line:
            line += " {userFq}"
        lines.append(line)
    return "\n".join(lines) + "\n"
authorizedKeysFile.write_text(getAuthorizedKeys(userFq))

sshHostPrivKeyFile = sshDir / "ssh_host_key"
sshHostPubKeyFile = sshDir / "ssh_host_key.pub"
sshHostPrivKeyFile.write_text(getVariable("sshServerPrivKey").strip() + "\n")
sshHostPubKeyFile.write_text(getVariable("sshServerPubKey").strip() + "\n")
sp_run(["chmod", "600", str(sshHostPrivKeyFile)], check=True)
sp_run(["chmod", "644", str(sshHostPubKeyFile)], check=True)

knownHostsFile = sshDir / "known_hosts"
knownHostsFile.write_text("|1|D/2nTwnJjvwViCqC+er4b6gZuWI=|tkb6jKufo0pkRHwNbr35P8WEcjc= ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQDF0YJigZJU62vn4rsKGRjIRTtMe/suc3d4YDe0iIvFzLMuaN78oxhWn9Uqefe1gN++dYVssspsgsvTXTTBcxxo3WoFeNr1z/+osJ45+Yxoa0pbaJdAwbr8CqjDa96r9/AhAXHoKncAByEOSiXfdWCXf84YC+Hu48/gZOqSZ3VqPz+nNGFByJcqYJ+jSELSqCNWVLWFxx7vH270Kymw2XkdOW47zzDNO7X4uByxHfaZMgI6phoaNglGizM0VNMQPL5GbspVGejFQE85QJbX3oF8vuCYnM+OMkwopHG+muh6Tro8+fm6G/fcmu34YJNbU3oaTdW1YPqvcKFX1AuIY9CA5lLZR9A1rOJ+fd4JEYaoTxwUN2ZPcrf7JEnvHmcV9hmupTSllJzLk4smDpl5PSknDm68/h/z/ZmaDlunGsHnn397fwCwS7sO9Q1yIuZ+Bri0td7+N2EK1mvM/qsnrSauOymcmqYVy6TLiejHdoVl8+lKqatkTxyFf/3MP8ylCKSoP0SJZratcU1n+0EciG+IjEzdPZ/1tuJZhBWqOUbYfUl+WgovH+J+AQKtoNzPP+fLtLNcmLEhx99N2y5l7A8IOlyy41Minq4N7V5X8Q7QHhEoocatNNn5JRYe/25P9aQelF0ItMD0PEmf8rIHWMqbwnwQ8pVVdDhE6mwhDskBIw==")

sshdConfigFile = sshDir / "sshd_config"
sshdConfigFile.write_text(f"""
Port 2222
HostKey {str(sshDir)}/ssh_host_key
PidFile {str(sshDir)}/sshd.pid
AuthorizedKeysFile {str(sshDir)}/authorized_keys
StrictModes no
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
""")


#install sshd
sshTunnelPath = Path(__file__).resolve().parent
pkgPath = sshTunnelPath / "openssh-server_8.9p1-3ubuntu0.17_amd64.deb"
checksumSshdPkg = subprocess.run(["sha256sum", str(pkgPath)], capture_output=True, text=True, check=True)
expectedChecksum = f"2baa4f236eebc486ec351ade604f1929286ede9ec3e2858a7206ddc412e3cbb6  {pkgPath}"
if checksumSshdPkg.stdout.rstrip() != expectedChecksum or checksumSshdPkg.stderr:
    raise Exception(f"openssh-server.deb did not match expected checksum, or produced an unexpected stderr output\nExpected checksum: {expectedChecksum}\n  Actual checksum: {checksumSshdPkg.stdout.rstrip()}\nstderr output: {checksumSshdPkg.stderr}")
else:
    print2(expectedChecksum)

dpkgDir = sshDir / "sshd"
sp_run(["dpkg-deb", "-x", str(pkgPath), str(dpkgDir)], check=True)
sshdPath = dpkgDir / "usr/sbin/sshd"


sshdProc = None
@keyword
def start_sshd():
    global sshdProc
    print2(f"Starting sshd daemon as {userFq}")
    sshdProc = sp_run([str(sshdPath), "-f", str(sshdConfigFile)], check=True)
    print2("Successfully started sshd daemon")

#TODO stop sshd
#TODO when start_sshd runs, check whether sshd is already running using psutil



sshTunnelBashScript = sshTunnelPath / "ssh_tunnel.sh"
sshTunnelBashScriptPidFile = sshTunnelPath / "ssh_tunnel_sh.pid"
sshTunnelOutputCleaner = sshTunnelPath / "ping_io_output_cleaner.py"
sp_run(["chmod", "+x", str(sshTunnelBashScript)], check=True)
sp_run(["chmod", "+x", str(sshTunnelOutputCleaner)], check=True)


@not_keyword
def getTunnelPid() -> int|None:
    pidFile = Path(sshTunnelBashScriptPidFile)
    if not pidFile.exists():
        return None
    elif not pidFile.is_file():
        raise Exception(f"{pidFile} exists but is not a file")
    pid = pidFile.read_text().strip()
    if not pid:
        return None
    try:
        return int(pid)
    except ValueError as e:
        raise ValueError(f"Invalid process id in file {sshTunnelBashScriptPidFile} : {repr(pid)}")


@keyword
def start_tunnel():
    pid = getTunnelPid()
    if pid is not None and psutil.pid_exists(pid):
        raise Exception(f"Tunnel already running, PID {pid}")
    print2("Starting tunnel...")
    os.system(f"{shlex.quote(str(sshTunnelBashScript))} {shlex.quote(str(sshTunnelBashScriptPidFile))} 2>&1 | python {shlex.quote(str(sshTunnelOutputCleaner))} &")


@keyword
def stop_tunnel():
    pid = getTunnelPid()
    if pid is None or not psutil.pid_exists(pid):
        raise Exception(f"Tunnel already stopped")
    print2("Stopping tunnel...")
    Path(sshTunnelBashScriptPidFile).unlink(missing_ok=True)
    os.system(f"kill {pid} >&2")
    for i in range (15):
        BuiltIn().sleep("1s")
        if not psutil.pid_exists(pid):
            return
    print2("Stopping tunnel failed, trying kill -9")
    for i in range (15):
        os.system(f"kill -9 {pid} >&2")
        BuiltIn().sleep("1s")
        if not psutil.pid_exists(pid):
            return
    raise Exception(f"Couldn't kill PID {pid}, even with kill -9") 

start_sshd()
start_tunnel()
