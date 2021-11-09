# Quick shorthand for testing
from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.cred2 import Rajni

import scxconf

if __name__ == "__main__":

    mode = 0

    # Prepare dependent processes
    tcp_recv = RemoteDependentProcess(
        tmux_name=f'streamTCPreceive_{scxconf.RAJNI_PORT}',
        # Urrrrrh this is getting messy
        cli_cmd=
        'milk-exec "creasshortimshm %s %u %u"; shmimTCPreceive -c ircam ' +
        f'{scxconf.RAJNI_PORT}',
        cli_args=('rajni', 320, 256),
        remote_host=scxconf.IP_SC6_LAN,
        kill_upon_create=False,
    )
    tcp_recv.start_order = 0
    tcp_recv.kill_order = 1

    tcp_send = DependentProcess(
        tmux_name='rajni_tcp',
        cli_cmd=
        'sleep 3; OMP_NUM_THREADS=1 /home/scexao/bin/shmimTCPtransmit %s %s %u',
        cli_args=('rajni', scxconf.IP_SC6_P2P70, scxconf.RAJNI_PORT),
        # Sender is kill_upon_create - rather than when starting. that ensures it dies well before the receiver
        # Which is better for flushing TCP sockets
        kill_upon_create=True,
        cset='rajni_tcp',
        rtprio=40,
    )
    tcp_send.start_order = 1
    tcp_send.kill_order = 0

    cam = Rajni('rajni',
                'rajni',
                unit=3,
                channel=0,
                mode_id=mode,
                taker_cset_prio=('rajni_edt', 41),
                dependent_processes=[tcp_recv, tcp_send])

    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())
