import os

from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.cred2 import Kiwikiu
from camstack.core.logger import init_camstack_logger
import scxconf
from scxkw.config import MAGIC_HW_STR

if __name__ == "__main__":

    os.makedirs(os.environ['HOME'] + "/logs", exist_ok=True)
    init_camstack_logger(os.environ['HOME'] + "/logs/camstack-kiwikiu.log")

    mode = 0

    # Prepare dependent processes
    tcp_recv = RemoteDependentProcess(
            tmux_name=f'streamTCPreceive_{scxconf.TCPPORT_KIWIKIU}',
            # Urrrrrh this is getting messy
            cli_cmd=
            'milk-exec "creasshortimshm %s %u %u"; shmimTCPreceive -c ircam ' +
            f'{scxconf.TCPPORT_KIWIKIU}',
            cli_args=('kiwikiu', MAGIC_HW_STR.HEIGHT, MAGIC_HW_STR.WIDTH),
            remote_host=scxconf.IP_SC6,
            kill_upon_create=False,
    )
    tcp_recv.start_order = 0
    tcp_recv.kill_order = 1

    tcp_send = DependentProcess(
            tmux_name='kiwikiu_tcp',
            cli_cmd='sleep 3; OMP_NUM_THREADS=1 shmimTCPtransmit %s %s %u',
            cli_args=('kiwikiu', scxconf.IPP2P_SC6FROM5,
                      scxconf.TCPPORT_KIWIKIU),
            # Sender is kill_upon_create - rather than when starting. that ensures it dies well before the receiver
            # Which is better for flushing TCP sockets
            kill_upon_create=True,
            cset='k_work',
            rtprio=44,
    )
    tcp_send.start_order = 1
    tcp_send.kill_order = 0

    cam = Kiwikiu('kiwikiu', 'kiwikiu', unit=3, channel=0, mode_id=mode,
                  taker_cset_prio=('k_work', 45),
                  dependent_processes=[tcp_recv, tcp_send])

    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())

    # PYROSERVER
    from scxconf import PYRONS3_HOST, PYRONS3_PORT, IP_SC5
    from camstack import pyro_keys as pk
    from swmain.network.pyroserver_registerable import PyroServer

    server = PyroServer(bindTo=(IP_SC5, 0),
                        nsAddress=(PYRONS3_HOST, PYRONS3_PORT))
    server.add_device(cam, pk.KIWIKIU, add_oneway_callables=True)
    server.start()
