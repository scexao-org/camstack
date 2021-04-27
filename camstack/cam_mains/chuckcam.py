# Quick shorthand for testing
from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.cred2 import Chuck

if __name__ == "__main__":

    mode = 0

    # Prepare dependent processes
    tcp_recv = RemoteDependentProcess(
        tmux_name='streamTCPreceive_30101',
        # Urrrrrh this is getting messy
        cli_cmd='milk-exec "creaushortimshm %s %u %u"; shmimTCPreceive -c ircam 30101',
        cli_args=('ircam0', 320, 256),
        remote_host='133.40.161.194',
        kill_upon_create = False,
    )
    tcp_recv.start_order = 0
    tcp_recv.kill_order = 0

    tcp_send = DependentProcess(
        tmux_name='ircam0_tcp',
        cli_cmd='sleep 3; OMP_NUM_THREADS=1 /home/scexao-op/bin/shmimTCPtransmit-simple %s %s %u',
        cli_args=('ircam0', '10.20.20.2', 30101),
        kill_upon_create = False,
        cset='ircam0_tcp',
        rtprio=49,
    )
    tcp_send.start_order = 1
    tcp_send.kill_order = 1

    cam = Chuck('ircam0',
                 'ircam0',
                  unit=0,
                  channel=0,
                  mode_id=mode,
                  taker_cset_prio=('ircam0_edt', 49),
                  dependent_processes=[tcp_recv, tcp_send])

    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())
