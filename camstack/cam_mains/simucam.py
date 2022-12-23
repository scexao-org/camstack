import os

from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.simulatedcam import SimulatedCam
from camstack.core.logger import init_camstack_logger

import scxconf
from scxkw.config import MAGIC_HW_STR

if __name__ == "__main__":

    os.makedirs(os.environ['HOME'] + "/logs", exist_ok=True)
    init_camstack_logger(os.environ['HOME'] + "/logs/camstack-sim.log")

    mode = 0

    # Prepare dependent processes
    tcp_recv = RemoteDependentProcess(
            tmux_name=f'streamTCPreceive_{scxconf.TCPPORT_RAJNI}',
            # Urrrrrh this is getting messy
            cli_cmd='shmimTCPreceive -c ircam ' + f'{scxconf.TCPPORT_RAJNI}',
            cli_args=(),
            remote_host=scxconf.IP_SC6,
            kill_upon_create=False,
    )
    tcp_recv.start_order = 0
    tcp_recv.kill_order = 1

    tcp_send = DependentProcess(
            tmux_name='simuquest_tcp',
            cli_cmd='sleep 3; OMP_NUM_THREADS=1 shmimTCPtransmit %s %s %u',
            cli_args=('simuquest', scxconf.IPP2P_SC6FROM5,
                      scxconf.TCPPORT_RAJNI),
            # Sender is kill_upon_create - rather than when starting. that ensures it dies well before the receiver
            # Which is better for flushing TCP sockets
            kill_upon_create=True,
            cset='rajni_tcp',
            rtprio=10,
    )
    tcp_send.start_order = 1
    tcp_send.kill_order = 0

    cam = SimulatedCam('simuquest', 'simuquest', mode_id=(2048, 512),
                       taker_cset_prio=('rajni_edt', 41),
                       dependent_processes=[tcp_recv, tcp_send])

    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())
