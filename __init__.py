import subprocess, sys
from pathlib import Path

from robot.libraries.BuiltIn import BuiltIn
from robot.api.deco import keyword, not_keyword


ROBOT_AUTO_KEYWORDS = False


@not_keyword
def getVariable(varName: str):
    BuiltIn().variable_should_exist(f"\\${{{varName}}}")
    value = BuiltIn().get_variable_value(f"\\${{{varName}}}")
    if not (value and isinstance(value, str) and value.lower() != "none"):
        raise ValueError(f"Variable ${{{varName}}} is Falsey or not a string: {repr(value)}")
    return value

def print2(*args):
    print(*args, file=sys.stderr)


sshTunnelPath = Path(__file__).resolve().parent
sshTunnelBashScript = sshTunnelPath / "ssh_tunnel.sh"
subprocess.run(["chmod", "+x", str(sshTunnelBashScript)], check=True)


hostname = subprocess.run(["hostname"], check=True, stdout=subprocess.PIPE, text=True).stdout.strip()
user = subprocess.run(["whoami"], check=True, stdout=subprocess.PIPE, text=True).stdout.strip()
userFq = f"{user}@{hostname}" # user fully-qualified name

sshDir = Path("~/.ssh").expanduser().resolve()
sshDir.mkdir(parents=True, exist_ok=True)
subprocess.run(["chmod", "700", str(sshDir)], stdout=sys.stderr, check=True)

authorizedKeysFile = sshDir / "authorized_keys"
authorizedKeysFile.write_text(f"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIA98UPhjY8FLkppMwQeNZAU6EW8UGKt9oB4clH5ne62X {userFq}\n")

sshHostPrivKeyFile = sshDir / "ssh_host_key"
sshHostPubKeyFile = sshDir / "ssh_host_key.pub"
sshHostPrivKeyFile.write_text(getVariable("privKey").strip() + "\n")
sshHostPubKeyFile.write_text("ssh-ed25519 " +  getVariable("pubKey").strip() + "\n")
subprocess.run(["chmod", "600", str(sshHostPrivKeyFile)], stdout=sys.stderr, check=True)
subprocess.run(["chmod", "644", str(sshHostPubKeyFile)], stdout=sys.stderr, check=True)

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

pkgPath = sshTunnelPath / "openssh-server_8.9p1-3ubuntu0.17_amd64.deb"
checksumSshdPkg = subprocess.run(["sha256sum", str(pkgPath)], capture_output=True, text=True, check=True)
expectedChecksum = f"2baa4f236eebc486ec351ade604f1929286ede9ec3e2858a7206ddc412e3cbb6  {pkgPath}"
if checksumSshdPkg.stdout.rstrip() != expectedChecksum or checksumSshdPkg.stderr:
    raise Exception(f"openssh-server.deb did not match expected checksum, or produced an unexpected stderr output\nExpected checksum: {expectedChecksum}\n  Actual checksum: {checksumSshdPkg.stdout.rstrip()}\nstderr output: {checksumSshdPkg.stderr}")
else:
    print2(checksumSshdPkg)

dpkgDir = sshDir / "sshd"
subprocess.run(["dpkg-deb", "-x", str(pkgPath), str(dpkgDir)], stdout=sys.stderr, check=True)
sshdPath = dpkgDir / "usr/sbin/sshd"


tunnelProc = None
sshdProc = None

@keyword
def start_sshd():
    global sshdProc
    print2(f"Starting sshd daemon as {userFq}...")
    sshdProc = subprocess.run([str(sshdPath), "-f", str(sshdConfigFile)], stdout=sys.stderr, check=True)
    print2("Sshd daemon successfully started")

#TODO stop sshd
#TODO when start_sshd runs, check whether sshd is already running using psutil


@keyword
def start_tunnel():
    global tunnelProc
    if tunnelProc:
        raise Exception("Tunnel is already running")
    print2("Starting tunnel...")
    tunnelProc = subprocess.Popen([str(sshTunnelBashScript)], stdout=sys.stderr)


@keyword
def stop_tunnel():
    global tunnelProc
    if tunnelProc is None:
        raise Exception("No tunnel running")
    print2("Stopping tunnel...")
    tunnelProc.terminate()
    try:
        tunnelProc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        tunnelProc.kill()
    tunnelProc = None


start_sshd()
start_tunnel()
