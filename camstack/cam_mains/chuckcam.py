# Quick shorthand for testing
from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.cred2 import Chuck

import scxconf

if __name__ == "__main__":

    mode = 0

    # Prepare dependent processes
    tcp_recv = RemoteDependentProcess(
        tmux_name=f'streamTCPreceive_{scxconf.CHUCK_PORT}',
        # Urrrrrh this is getting messy
        cli_cmd='creashmim %s %u %u; shmimTCPreceive -c ircam ' +
        f'{scxconf.IP_SC6_LAN}',
        cli_args=('ircam0', 320, 256),
        remote_host=scxconf.IP_SC6_LAN,
        kill_upon_create=False,
    )
    tcp_recv.start_order = 1
    tcp_recv.kill_order = 1

    tcp_send = DependentProcess(
        tmux_name='ircam0_tcp',
        cli_cmd=
        'sleep 3; OMP_NUM_THREADS=1 /home/scexao-op/bin/shmimTCPtransmit-simple %s %s %u',
        cli_args=('ircam0', scxconf.IP_SC6_LAN, scxconf.CHUCK_PORT),
        # Sender is kill_upon_create - rather than when starting. that ensures it dies well before the receiver
        # Which is better for flushing TCP sockets
        kill_upon_create=True,
        cset='ircam0_tcp',
        rtprio=49,
    )
    tcp_send.start_order = 2
    tcp_send.kill_order = 0

    utr_red = DependentProcess(
        tmux_name='ircam0_utr',
        cli_cmd=
        'milk-exec "mload milkimageformat; readshmim ircam0_raw; imgformat.cred_ql_utr ..procinfo 1; '
        'imgformat.cred_ql_utr ..triggermode 3; imgformat.cred_ql_utr ..loopcntMax -1; '
        'imgformat.cred_ql_utr ircam0_raw ircam0 5000"',
        cli_args=(),
        kill_upon_create=True,
        cset='ircam0_utr',
        rtprio=49,
    )
    utr_red.start_order = 0
    utr_red.kill_order = 2

    cam = Chuck('ircam0',
                'ircam0_raw',
                unit=0,
                channel=0,
                mode_id=mode,
                taker_cset_prio=('ircam0_edt', 49),
                dependent_processes=[tcp_recv, tcp_send, utr_red])

    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())
