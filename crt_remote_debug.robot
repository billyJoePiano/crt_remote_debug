*** Settings ***
Library                         ./crt_remote_debug.py

*** Variables ***
# REQUIRED VARIABLES!           These must be set as project, robot, or test-job level variables within Copado Robotic Testing
# ${sshPrivKey}
# ${sshPubKey}
# ${sshServerAuthorizedClientsPubKeys}
# NOTE: these are commented out to prevent overwritting pre-existing values at runtime



# Server public key fingerprint for free.pinggy.io, which provides a free public tunnel endpoint.
# This fingerprint is used to verify the authenticity of the ping.io server when connecting to it via ssh client
# TODO make the hostname plaintext rather than hashed
${PINGGY_IO_SERVER_KEYHASH}     |1|D/2nTwnJjvwViCqC+er4b6gZuWI=|tkb6jKufo0pkRHwNbr35P8WEcjc= ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQDF0YJigZJU62vn4rsKGRjIRTtMe/suc3d4YDe0iIvFzLMuaN78oxhWn9Uqefe1gN++dYVssspsgsvTXTTBcxxo3WoFeNr1z/+osJ45+Yxoa0pbaJdAwbr8CqjDa96r9/AhAXHoKncAByEOSiXfdWCXf84YC+Hu48/gZOqSZ3VqPz+nNGFByJcqYJ+jSELSqCNWVLWFxx7vH270Kymw2XkdOW47zzDNO7X4uByxHfaZMgI6phoaNglGizM0VNMQPL5GbspVGejFQE85QJbX3oF8vuCYnM+OMkwopHG+muh6Tro8+fm6G/fcmu34YJNbU3oaTdW1YPqvcKFX1AuIY9CA5lLZR9A1rOJ+fd4JEYaoTxwUN2ZPcrf7JEnvHmcV9hmupTSllJzLk4smDpl5PSknDm68/h/z/ZmaDlunGsHnn397fwCwS7sO9Q1yIuZ+Bri0td7+N2EK1mvM/qsnrSauOymcmqYVy6TLiejHdoVl8+lKqatkTxyFf/3MP8ylCKSoP0SJZratcU1n+0EciG+IjEzdPZ/1tuJZhBWqOUbYfUl+WgovH+J+AQKtoNzPP+fLtLNcmLEhx99N2y5l7A8IOlyy41Minq4N7V5X8Q7QHhEoocatNNn5JRYe/25P9aQelF0ItMD0PEmf8rIHWMqbwnwQ8pVVdDhE6mwhDskBIw==




# Optional variables that can be set/overridden for custom configurations

# local ports for the CRT cloud container
${localSshServerPort}           2222
${localDebugpyPort}             5678                        # local
${remoteForwardedSshServerPort}                             2222
${remoteForwardedDebugpyPort}                               5678

${sshTunnelRemoteUser}
${sshTunnelRemoteHost}
${sshTunnelRemoteSshPort}


${sshClientKnownHosts}          ${PINGGY_IO_SERVER_KEYHASH}
${sshClientHashKnownHosts}      ${False}
@{sshTunnelRemotePortForwardsPublic}                        0:localhost:${localSshServerPort}                       #default for free.pinggy.io public tunnel.
@{sshTunnelRemotePortForwardsPrivate}                       localhost:${remoteForwardedSshServerPort}:localhost:${localSshServerPort}           localhost:${remoteForwardedDebugpyPort}:localhost:${localDebugpyPort}


*** Keywords ***
Configure And Start Public Debug Tunnel
    # The default free.pinggy.iotunnel will forward your ssh connection from a public+ephemeral host and port to the CRT cloud container's local ssh port.
    # The public+ephemeral host and port number will be outputed by the pinggy.io server upon initiating the tunnel,
    # and will be readable via the CRT cloud container's console output

    ${sshClientHashKnownHosts}=                             Convert To Boolean          ${sshClientHashKnownHosts}
    ${localSshServerPort}=      Convert To Integer          ${localSshServerPort}
    ${localDebugpyPort}=        Convert To Integer          ${localDebugpyPort}


    Configure Ssh Host Key      ${sshPrivKey}               ${sshPubKey}
    Configure Ssh Client        ${sshClientKnownHosts}      ${sshClientHashKnownHosts}
    Configure Ssh Server        ${sshServerAuthorizedClientsPubKeys}                    ${localSshServerPort}

    Install Openssh Server If Needed
    Start Ssh Server

    Start Debugpy               addr=localhost              port=${localDebugpyPort}

    Start Free Pinggy Io Tunnel


 Configure And Start Private Debug Tunnel
    [Arguments]                 ${startSshServer}=${True}
    # This should only be used when connecting to a private tunnel endpoint, because the debugpy port is forwarded from the tunnel endpoint without any authentication and is unencrypted
    # Typically, a private tunnel would be created through port-forwarding the incoming ssh connection via your home/office router to your local workstation.
    # The local workstation would be running its own ssh server that is configured to only allow connections from the known public key of the CRT cloud container,
    # (provided in the ${sshPubKey} variable), and the tunnel endpoints would only be accessible from the local workstation's "localhost" loopback interface.

    ${sshClientHashKnownHosts}=                             Convert To Boolean          ${sshClientHashKnownHosts}
    ${localDebugpyPort}=        Convert To Integer          ${localDebugpyPort}


    Configure Ssh Host Key      ${sshPrivKey}               ${sshPubKey}
    Configure Ssh Client        ${sshClientKnownHosts}      ${sshClientHashKnownHosts}

    IF                          ${startSshServer}
        ${localSshServerPort}=                              Convert To Integer          ${localSshServerPort}
        Install Openssh Server If Needed
        Configure Ssh Server    ${sshServerAuthorizedClientsPubKeys}                    ${localSshServerPort}
        Start Ssh Server
    END

    Start Debugpy               addr=localhost              port=${localDebugpyPort}

    Start Tunnel


Start Free Pinggy Io Tunnel
    Start Free Pinggy Io Tunnel Handler                     @{sshTunnelRemotePortForwardsPublic}


Start Tunnel
    Start Tunnel Handler        ${sshTunnelRemoteUser}               ${sshTunnelRemoteHost}               ${sshTunnelRemoteSshPort}            @{sshTunnelRemotePortForwardsPrivate}
