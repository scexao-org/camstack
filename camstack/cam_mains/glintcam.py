# Quick shorthand for testing
from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.cred2 import GLINT

import os

if __name__ == "__main__":

    mode = 12
    port = 30109

    # Prepare dependent processes
    tcp_recv = RemoteDependentProcess(
        tmux_name='streamTCPreceive_' + str(port),
        # Urrrrrh this is getting messy
        cli_cmd='milk-exec "creasshortimshm %s %u %u"; shmimTCPreceive -c ircam ' + str(port),
        cli_args=('glint', 320, 256),
        remote_host='133.40.161.194',
        kill_upon_create = False,
    )
    tcp_recv.start_order = 0
    tcp_recv.kill_order = 1

    tcp_send = DependentProcess(
        tmux_name='glint_tcp',
        cli_cmd='sleep 3; OMP_NUM_THREADS=1 /home/scexao/bin/shmimTCPtransmit %s %s %u',
        cli_args=('glint', '10.20.70.1', port),
        # Sender is kill_upon_create - rather than when starting. that ensures it dies well before the receiver
        # Which is better for flushing TCP sockets
        kill_upon_create = True, 
        cset='glint_tcp',
        rtprio=40,
    )
    tcp_send.start_order = 1
    tcp_send.kill_order = 0

    try:
        os.makedirs(os.environ['MILK_SHM_DIR'] + '/smb') # Samba server root
    except FileExistsError:
        pass

    fits_dump = DependentProcess(
        tmux_name = 'glint_fits',
        cli_cmd='OMP_NUM_THREADS=1 shmim2rollingFits %s %s %d',
        cli_args=('glint', os.environ['MILK_SHM_DIR'] + "/smb/", .05),
        kill_upon_create=False,
    )
    fits_dump.start_order = 2
    fits_dump.kill_order = 2


    cam = GLINT('glint',
                 'glint',
                  unit=2,
                  channel=0,
                  mode_id=mode,
                  taker_cset_prio=('glint_edt', 41),
                  dependent_processes=[tcp_recv, tcp_send, fits_dump])

    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())
