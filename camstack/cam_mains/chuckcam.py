# Quick shorthand for testing
from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.cred2 import Chuck

if __name__ == "__main__":

    mode = 0
    port = 30101

    # Prepare dependent processes
    tcp_recv = RemoteDependentProcess(
        tmux_name='streamTCPreceive_' + str(port),
        # Urrrrrh this is getting messy
        cli_cmd='milk-exec "creasshortimshm %s %u %u"; shmimTCPreceive -c ircam ' + str(port),
        cli_args=('ircam0', 320, 256),
        remote_host='133.40.161.194',
        kill_upon_create = False,
    )
    tcp_recv.start_order = 0
    tcp_recv.kill_order = 1

    tcp_send = DependentProcess(
        tmux_name='ircam0_tcp',
        cli_cmd='sleep 3; OMP_NUM_THREADS=1 /home/scexao-op/bin/shmimTCPtransmit-simple %s %s %u',
        cli_args=('ircam0', '10.20.20.2', port),
        # Sender is kill_upon_create - rather than when starting. that ensures it dies well before the receiver
        # Which is better for flushing TCP sockets
        kill_upon_create = True,
        cset='ircam0_tcp',
        rtprio=49,
    )
    tcp_send.start_order = 1
    tcp_send.kill_order = 0

    cam = Chuck('ircam0',
                 'ircam0',
                  unit=0,
                  channel=0,
                  mode_id=mode,
                  taker_cset_prio=('ircam0_edt', 49),
                  dependent_processes=[tcp_recv, tcp_send])

    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())
