# Quick shorthand for testing
from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.cred2 import Chuck

import scxconf

if __name__ == "__main__":

    mode = 0

    # Prepare dependent processes
    tcp_recv = RemoteDependentProcess(
        tmux_name=f'streamTCPreceive_{scxconf.TCPPORT_CHUCK}',
        # Urrrrrh this is getting messy
        cli_cmd='creashmim %s %u %u; shmimTCPreceive -c ircam ' +
        f'{scxconf.TCPPORT_CHUCK}',
        cli_args=('ircam0', 320, 256),
        remote_host='scexao@' + scxconf.IPLAN_SC6,
        kill_upon_create=False,
    )
    tcp_recv.start_order = 1
    tcp_recv.kill_order = 1

    tcp_send = DependentProcess(
        tmux_name='chuck_tcp',
        cli_cmd=
        'sleep 3; OMP_NUM_THREADS=1 shmimTCPtransmit %s %s %u',
        cli_args=('ircam0', scxconf.IPLAN_SC6, scxconf.TCPPORT_CHUCK),
        # Sender is kill_upon_create - rather than when starting. that ensures it dies well before the receiver
        # Which is better for flushing TCP sockets
        kill_upon_create=True,
        cset='chuck_tcp',
        rtprio=49,
    )
    tcp_send.start_order = 2
    tcp_send.kill_order = 0

    utr_red = DependentProcess(
        tmux_name='chuck_utr',
        cli_cmd=
        'milk-exec "mload milkimageformat; readshmim ircam0_raw; imgformat.cred_cds_utr ..procinfo 1; '
        'imgformat.cred_cds_utr ..triggermode 3; imgformat.cred_cds_utr ..loopcntMax -1; '
        'imgformat.cred_cds_utr ircam0_raw ircam0 5000"',
        cli_args=(),
        kill_upon_create=True,
        cset='chuck_utr',
        rtprio=49,
    )
    utr_red.start_order = 0
    utr_red.kill_order = 2

    # PIPE over ZMQ into the LAN until we find a better solution (receiver)
    zmq_recv = RemoteDependentProcess(
        tmux_name='chuck_zmq',
        cli_cmd='zmq_recv.py %s:%u %s',
        cli_args=(scxconf.IPLAN_SC5, scxconf.ZMQPORT_CHUCK, 'ircam0'),
        remote_host=f'scexao-op@{scxconf.IP_SC2}',
        kill_upon_create=False,
    )
    zmq_recv.start_order = 4
    zmq_recv.kill_order = 5

    # PIPE over ZMQ into the LAN until we find a better solution (sender)
    zmq_send = DependentProcess(
        tmux_name='chuck_zmq',
        cli_cmd='zmq_send.py %s:%u %s -f 100',
        cli_args=(scxconf.IPLAN_SC5, scxconf.ZMQPORT_CHUCK, 'ircam0'),
        kill_upon_create=True,
    )
    zmq_send.start_order = 5
    zmq_send.kill_order = 4

    cam = Chuck('ircam0',
                'ircam0_raw',
                unit=4,
                channel=0,
                mode_id=mode,
                taker_cset_prio=('chuck_edt', 49),
                dependent_processes=[tcp_recv, tcp_send, utr_red, zmq_recv, zmq_send])

    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())
