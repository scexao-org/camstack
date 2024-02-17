import os

from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.dcamcam import FIRSTOrcam

from scxkw.config import MAGIC_HW_STR
import scxconf

from camstack.core.logger import init_camstack_logger

if __name__ == "__main__":

    os.makedirs(os.environ['HOME'] + "/logs", exist_ok=True)
    init_camstack_logger(os.environ['HOME'] + "/logs/camstack-firstcam.log")

    # mode = FIRSTOrcam.FIRST
    mode = FIRSTOrcam.FIRSTPL
    # mode = FIRSTOrcam.FULL
    # mode = OrcaQuest.FULL

    # Prepare dependent processes
    tcp_recv = RemoteDependentProcess(
            tmux_name=f'streamTCPreceive_{scxconf.TCPPORT_FIRST_ORCA}',
            # Urrrrrh this is getting messy
            cli_cmd='creashmim %s %u %u --kw=300; shmimTCPreceive -c tcprecv1 '
            + f'{scxconf.TCPPORT_FIRST_ORCA}',
            cli_args=('orcam', MAGIC_HW_STR.HEIGHT, MAGIC_HW_STR.WIDTH),
            remote_host='scexao@' + scxconf.IPLAN_SC6,
            kill_upon_create=False,
    )
    tcp_recv.start_order = 1
    tcp_recv.kill_order = 1

    tcp_send = DependentProcess(
            tmux_name='first_tcp',
            cli_cmd='sleep 3; OMP_NUM_THREADS=1 shmimTCPtransmit %s %s %u',
            cli_args=('orcam', scxconf.IPLAN_SC6, scxconf.TCPPORT_FIRST_ORCA),
            # Sender is kill_upon_create - rather than when starting. that ensures it dies well before the receiver
            # Which is better for flushing TCP sockets
            kill_upon_create=True,
            cset='system',
            rtprio=45,
    )
    tcp_send.start_order = 2
    tcp_send.kill_order = 0

    cam = FIRSTOrcam('orcam', 'orcam', dcam_number=0, mode_id=mode,
                     taker_cset_prio=('user', 42),
                     dependent_processes=[tcp_recv, tcp_send])

    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())

    # PYROSERVER
    from scxconf import PYRONS3_HOST, PYRONS3_PORT
    from camstack import pyro_keys as pk
    from swmain.network.pyroserver_registerable import PyroServer

    server = PyroServer(nsAddress=(PYRONS3_HOST, PYRONS3_PORT))
    server.add_device(cam, pk.FIRST, add_oneway_callables=True)
    server.start()
