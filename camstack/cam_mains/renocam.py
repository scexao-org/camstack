# Quick shorthand for testing
from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.ocam import OCAM2K

if __name__ == "__main__":

    binning, mode = True, 3

    # Prepare dependent processes
    
    
    ocam_decode = DependentProcess(
        tmux_name='ocam_decode',
        cli_cmd='/home/scexao/src/camstack/ocamdecode/ocamdecoderun_mode %u',
        cli_args=(mode,),
        kill_upon_create = False,
        cset='ocam_decode',
        rtprio=48,
    )
    ocam_decode.start_order = 0
    ocam_decode.kill_order = 2
    
    
    tcp_recv = RemoteDependentProcess(
        tmux_name='streamTCPreceive_30107',
        # Urrrrrh this is getting messy
        cli_cmd='milk-exec "creaushortimshm %s %u %u"; shmimTCPreceive -c aol0COM 30107',
        cli_args=('ocam2dalt', 120, 120),
        remote_host='133.40.161.194',
        kill_upon_create = False,
    )
    tcp_recv.start_order = 1
    tcp_recv.kill_order = 0

    tcp_send = DependentProcess(
        tmux_name='ocam_tcp',
        cli_cmd='sleep 3; OMP_NUM_THREADS=1 /home/scexao/bin/shmimTCPtransmit %s %s %u',
        cli_args=('ocam2dalt', '10.20.70.1', 30107),
        kill_upon_create = False,
        cset='ocam_tcp',
        rtprio=49,
    )
    tcp_send.start_order = 2
    tcp_send.kill_order = 1

    ocam = OCAM2K('ocam',
                  'ocam2krc',
                  'ocam2dalt',
                  unit=3,
                  channel=0,
                  binning=binning,
                  taker_cset_prio=('ocam_edt', 49),
                  dependent_processes=[ocam_decode, tcp_recv, tcp_send])
    from camstack.core.utilities import shellify_methods
    shellify_methods(ocam, globals())