*** Settings ***
Library                         ./crt_remote_debug.py

*** Variables ***
#required
${sshPrivKey}
${sshPubKey}
${sshServerAuthorizedClientsPubKeys}


# Server public key fingerprint for free.pinggy.io, which provides a free public tunnel endpoint. Used to verify the authenticity of the ping.io server when connecting to it via ssh client
# TODO make the hostname plaintext rather than hashed
${PINGGY_IO_SERVER_KEYHASH}     |1|D/2nTwnJjvwViCqC+er4b6gZuWI=|tkb6jKufo0pkRHwNbr35P8WEcjc= ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQDF0YJigZJU62vn4rsKGRjIRTtMe/suc3d4YDe0iIvFzLMuaN78oxhWn9Uqefe1gN++dYVssspsgsvTXTTBcxxo3WoFeNr1z/+osJ45+Yxoa0pbaJdAwbr8CqjDa96r9/AhAXHoKncAByEOSiXfdWCXf84YC+Hu48/gZOqSZ3VqPz+nNGFByJcqYJ+jSELSqCNWVLWFxx7vH270Kymw2XkdOW47zzDNO7X4uByxHfaZMgI6phoaNglGizM0VNMQPL5GbspVGejFQE85QJbX3oF8vuCYnM+OMkwopHG+muh6Tro8+fm6G/fcmu34YJNbU3oaTdW1YPqvcKFX1AuIY9CA5lLZR9A1rOJ+fd4JEYaoTxwUN2ZPcrf7JEnvHmcV9hmupTSllJzLk4smDpl5PSknDm68/h/z/ZmaDlunGsHnn397fwCwS7sO9Q1yIuZ+Bri0td7+N2EK1mvM/qsnrSauOymcmqYVy6TLiejHdoVl8+lKqatkTxyFf/3MP8ylCKSoP0SJZratcU1n+0EciG+IjEzdPZ/1tuJZhBWqOUbYfUl+WgovH+J+AQKtoNzPP+fLtLNcmLEhx99N2y5l7A8IOlyy41Minq4N7V5X8Q7QHhEoocatNNn5JRYe/25P9aQelF0ItMD0PEmf8rIHWMqbwnwQ8pVVdDhE6mwhDskBIw==


#optional
${localSshServerPort}           2222
${localDebugpyPort}             5678
${remoteForwardedSshServerPort}                             2222
${remoteForwardedDebugpyPort}                               5678

${sshTunnelRemoteUser}          qr+tcp
${sshTunnelRemoteHost}          free.pinggy.io
${sshTunnelRemoteSshPort}       443


${sshClientKnownHosts}          ${PINGGY_IO_SERVER_KEYHASH}
${sshClientHashKnownHosts}      ${False}
@{tunnelRemotePortForwardsPublic}                           0:localhost:${localSshServerPort}    #default for free.pinggy.io public tunnel.
@{tunnelRemotePortForwardsPrivate}                          localhost:${remoteForwardedSshServerPort}:localhost:${localSshServerPort}    localhost:${remoteForwardedDebugpyPort}:localhost:${localDebugpyPort}


*** Keywords ***
Start Public Debug Tunnel
    # The default free.pinggy.iotunnel will forward your ssh connection from a public+ephemeral host and port to the CRT cloud container's local ssh port.
    # The public+ephemeral host and port number will be outputed by the pinggy.io server upon initiating the tunnel,
    # and will be readable via the CRT cloud container's console output

    Configure Ssh Host Key      ${sshPrivKey}               ${sshPubKey}

    ${sshClientHashKnownHosts}=                             Convert To Boolean          ${sshClientHashKnownHosts}
    ${localSshServerPort}=      Convert To Integer          ${localSshServerPort}
    ${localDebugpyPort}=        Convert To Integer          ${localDebugpyPort}

    Configure Ssh Client        ${sshClientKnownHosts}      ${sshClientHashKnownHosts}
    Configure Ssh Server        ${sshServerAuthorizedClientsPubKeys}                    ${localSshServerPort}

    Install OpenSshServer
    Start Ssh Server
    Start Free Pinggy Io Tunnel                             @{tunnelRemovePortForwardsPublic}
    Start Debugpy               addr=localhost              port=${localDebugpyPort}


Start Private Debug Tunnel
    [Arguments]                 ${startSshServer}=${True}
    # This should only be used when connecting to a private tunnel endpoint, because the debugpy port is forwarded from the tunnel endpoint without any authentication and is unencrypted
    # Typically, a private tunnel would be created through port-forwarding the incoming ssh connection via your home/office router to your local workstation.
    # The local workstation would be running its own ssh server that is configured to only allow connections from the known public key of the CRT cloud container,
    # (provided in the ${sshPubKey} variable), and the tunnel endpoints would only be accessible from the local workstation's "localhost" loopback interface.

    Configure Ssh Host Key      ${sshPrivKey}               ${sshPubKey}

    ${sshClientHashKnownHosts}=                             Convert To Boolean          ${sshClientHashKnownHosts}
    ${localDebugpyPort}=        Convert To Integer          ${localDebugpyPort}

    Configure Ssh Client        ${sshClientKnownHosts}      ${sshClientHashKnownHosts}

    IF                          ${startSshServer}
        ${localSshServerPort}=                              Convert To Integer          ${localSshServerPort}
        Install OpenSshServer
        Start Ssh Server
        Configure Ssh Server    ${sshServerAuthorizedClientsPubKeys}                    ${localSshServerPort}
    END

    Start Tunnel                @{tunnelRemovePortForwardsPublic}
    Start Debugpy               addr=localhost              port=${localDebugpyPort}