import os

from camstack.core import utilities as util
from camstack.cams.dcamcam import AlalaOrcam
from camstack.core.logger import init_camstack_logger

from scxkw.config import MAGIC_HW_STR
import scxconf

if __name__ == "__main__":

    os.makedirs(os.environ['HOME'] + "/logs", exist_ok=True)
    init_camstack_logger(os.environ['HOME'] + "/logs/camstack-orcam.log")

    mode = AlalaOrcam.FULL
    mode = AlalaOrcam.WFS
    '''
    TCPPORT_NLCWFS = scxconf.TCPPORT_FIRST_ORCA + 3 # No!

        # Prepare dependent processes
    tcp_recv = util.RemoteDependentProcess(
            tmux_name=f'streamTCPreceive_{TCPPORT_NLCWFS}',
            # Urrrrrh this is getting messy
            cli_cmd='creashmim %s %u %u --kw=300;  -c tcprecv3 '
            + f'{TCPPORT_NLCWFS}',
            cli_args=('orcam', MAGIC_HW_STR.HEIGHT, MAGIC_HW_STR.WIDTH),
            remote_host='scexao@' + scxconf.IPLAN_SC6,
            kill_upon_create=False,
    )

    tcp_send = util.DependentProcess(
            tmux_name='orcam_tcp',
            cli_cmd='sleep 3; OMP_NUM_THREADS=1 shmimUDPtransmit %s %s %u',
            cli_args=('orcam', scxconf.IPLAN_SC6, scxconf.TCPPORT_FIRST_ORCA+3),
            # Sender is kill_upon_create - rather than when starting. that ensures it dies well before the receiver
            # Which is better for flushing TCP sockets
            kill_upon_create=True,
            cset='system',
            rtprio=45,
    )

    util.process_ordering_start([tcp_recv, tcp_send, zmq_recv, zmq_send])
    util.process_ordering_stop([zmq_recv, zmq_send, tcp_recv, tcp_send])
    '''

    cam = AlalaOrcam('orcam', 'orcam', dcam_number=0, mode_id=mode,
                     taker_cset_prio=('user', 42), dependent_processes=[])

    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())

    # PYROSERVER
    from scxconf import PYRONSAO_HOST, PYRONSAO_PORT, IP_AORTS_SUMMIT
    from camstack import pyro_keys as pk
    from swmain.network.pyroserver_registerable import PyroServer

    server = PyroServer(bindTo=(IP_AORTS_SUMMIT, 0),
                        nsAddress=(PYRONSAO_HOST, PYRONSAO_PORT))
    server.add_device(cam, pk.ALALA, add_oneway_callables=True)
    server.start()
