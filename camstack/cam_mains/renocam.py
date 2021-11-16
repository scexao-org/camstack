# Quick shorthand for testing
from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.ocam import OCAM2K

import scxconf

if __name__ == "__main__":

    binning, mode = True, 3

    # Prepare dependent processes

    ocam_decode = DependentProcess(
        tmux_name='ocam_decode',
        cli_cmd=
        'cd /home/scexao/src/camstack/ocamdecode; /home/scexao/src/camstack/ocamdecode/ocamdecoderun_mode %u',
        cli_args=(mode, ),
        kill_upon_create=False,
        cset='ocam_decode',
        rtprio=48,
    )
    ocam_decode.start_order = 0
    ocam_decode.kill_order = 2

    tcp_recv = RemoteDependentProcess(
        tmux_name=f'streamTCPreceive_{scxconf.TCPPORT_OCAM}',
        # Urrrrrh this is getting messy
        cli_cmd=
        'milk-exec "creaushortimshm %s %u %u"; shmimTCPreceive -c aol0COM ' +
        f'{scxconf.TCPPORT_OCAM}',
        cli_args=('ocam2d', 120, 120),
        remote_host=scxconf.IPLAN_SC6,
        kill_upon_create=False,
    )
    tcp_recv.start_order = 1
    tcp_recv.kill_order = 1

    tcp_send = DependentProcess(
        tmux_name='ocam_tcp',
        cli_cmd=
        'sleep 3; OMP_NUM_THREADS=1 shmimTCPtransmit %s %s %u',
        cli_args=('ocam2d', scxconf.IPP2P_SC6FROM5, scxconf.TCPPORT_OCAM),
        # Sender is kill_upon_create - rather than when starting. that ensures it dies well before the receiver
        # Which is better for flushing TCP sockets
        kill_upon_create=True,
        cset='ocam_tcp',
        rtprio=49,
    )
    tcp_send.start_order = 2
    tcp_send.kill_order = 0

    cam = OCAM2K('ocam',
                 'ocam2krc',
                 'ocam2d',
                 unit=0,
                 channel=0,
                 binning=binning,
                 taker_cset_prio=('ocam_edt', 49),
                 dependent_processes=[ocam_decode, tcp_recv, tcp_send])
                 
    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())
