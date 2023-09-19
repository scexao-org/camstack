import os

from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.cred1 import Apapane

from camstack.core.logger import init_camstack_logger

from scxkw.config import MAGIC_HW_STR

import scxconf

if __name__ == "__main__":

    os.makedirs(os.environ['HOME'] + "/logs", exist_ok=True)
    init_camstack_logger(os.environ['HOME'] + "/logs/camstack-apapane.log")

    mode = 3

    # Prepare dependent processes
    tcp_recv = RemoteDependentProcess(
            tmux_name=f'streamTCPreceive_{scxconf.TCPPORT_APAPANE}',
            # Urrrrrh this is getting messy
            cli_cmd='creashmim %s %u %u --type=f32; shmimTCPreceive -c ircam ' +
            f'{scxconf.TCPPORT_APAPANE}',
            cli_args=('apapane', MAGIC_HW_STR.HEIGHT, MAGIC_HW_STR.WIDTH),
            remote_host=scxconf.IP_SC6,
            kill_upon_create=False,
    )
    tcp_recv.start_order = 1
    tcp_recv.kill_order = 1

    tcp_send = DependentProcess(
            tmux_name='apapane_tcp',
            cli_cmd='sleep 3; OMP_NUM_THREADS=1 shmimTCPtransmit %s %s %u',
            cli_args=('apapane', scxconf.IPP2P_SC6FROM5,
                      scxconf.TCPPORT_APAPANE),
            # Sender is kill_upon_create - rather than when starting. that ensures it dies well before the receiver
            # Which is better for flushing TCP sockets
            kill_upon_create=True,
            cset='a_tcp',
            rtprio=46,
    )
    tcp_send.start_order = 2
    tcp_send.kill_order = 0

    # TODO register those 2 to the "Apapane" object and make csets for them ?
    # Prepare dependent processes
    tcp_recv_raw = RemoteDependentProcess(
            tmux_name=f'streamTCPreceive_{scxconf.TCPPORT_APAPANE_RAW}',
            # Urrrrrh this is getting messy
            cli_cmd=  # FIXME
            'milk-exec "creashmim %s %u %u --type=u16"; shmimTCPreceive -c ircam '
            + f'{scxconf.TCPPORT_APAPANE_RAW}',
            cli_args=('apapane_raw', MAGIC_HW_STR.HEIGHT, MAGIC_HW_STR.WIDTH),
            remote_host=scxconf.IP_SC6,
            kill_upon_create=False,
    )
    tcp_recv.start_order = 3
    tcp_recv.kill_order = 4

    tcp_send_raw = DependentProcess(
            tmux_name='apapane_raw_tcp',
            cli_cmd='sleep 3; OMP_NUM_THREADS=1 shmimTCPtransmit %s %s %u',
            cli_args=('apapane_raw', scxconf.IP_SC6,
                      scxconf.TCPPORT_APAPANE_RAW),
            # Sender is kill_upon_create - rather than when starting. that ensures it dies well before the receiver
            # Which is better for flushing TCP sockets
            kill_upon_create=True,
            cset='a_tcp',
            rtprio=45,
    )
    tcp_send.start_order = 4
    tcp_send.kill_order = 3

    utr_red = DependentProcess(
            tmux_name='apapane_utr',
            cli_cmd=
            'milk-exec "mload milkimageformat; readshmim apapane_raw; imgformat.cred_cds_utr ..procinfo 1; imgformat.cred_cds_utr ..triggermode 3; imgformat.cred_cds_utr ..loopcntMax -1; imgformat.cred_cds_utr apapane_raw apapane 37000"',
            cli_args=(),
            kill_upon_create=True,
            cset='a_utr',
            rtprio=45,
    )
    utr_red.start_order = 0
    utr_red.kill_order = 2

    # PIPE over ZMQ into the LAN until we find a better solution (receiver)
    zmq_recv = RemoteDependentProcess(
            tmux_name='apapane_zmq',
            cli_cmd='zmq_recv.py %s:%u %s',
            cli_args=(scxconf.IPLAN_SC5, scxconf.ZMQPORT_APAPANE, 'apapane'),
            remote_host=f'scexao-op@{scxconf.IP_SC2}',
            kill_upon_create=False,
    )
    zmq_recv.start_order = 5
    zmq_recv.kill_order = 6

    # PIPE over ZMQ into the LAN until we find a better solution (sender)
    zmq_send = DependentProcess(
            tmux_name='apapane_zmq',
            cli_cmd='zmq_send.py %s:%u %s -f 100',
            cli_args=(scxconf.IPLAN_SC5, scxconf.ZMQPORT_APAPANE, 'apapane'),
            kill_upon_create=True,
    )
    zmq_send.start_order = 6
    zmq_send.kill_order = 5

    cam = Apapane('apapane', 'apapane_raw', unit=1, channel=0, mode_id=mode,
                  taker_cset_prio=('a_edt', 48), dependent_processes=[
                          tcp_recv, tcp_send, utr_red, zmq_recv, zmq_send
                  ])  #, tcp_send_raw, tcp_recv_raw])

    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())

    # PYROSERVER
    from scxconf import PYRONS3_HOST, PYRONS3_PORT, IP_SC5
    from camstack import pyro_keys as pk
    from swmain.network.pyroserver_registerable import PyroServer

    server = PyroServer(bindTo=(IP_SC5, 0),
                        nsAddress=(PYRONS3_HOST, PYRONS3_PORT))
    server.add_device(cam, pk.APAPANE, add_oneway_callables=True)
    server.start()
