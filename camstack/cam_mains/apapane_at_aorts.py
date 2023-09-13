import os

from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.cred1 import ApapaneAtAORTS

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
            cli_cmd='shmimTCPreceive -c ircam ' +
            f'{scxconf.TCPPORT_APAPANE}',
            cli_args=(),
            remote_host=scxconf.IP_SC6,
            kill_upon_create=False,
    )
    tcp_recv.start_order = 1
    tcp_recv.kill_order = 1

    tcp_send = DependentProcess(
            tmux_name='apapane_tcp',
            cli_cmd='sleep 3; OMP_NUM_THREADS=1 shmimTCPtransmit %s %s %u',
            cli_args=('apapane', scxconf.IPLAN_SC6,
                      scxconf.TCPPORT_APAPANE),
            # Sender is kill_upon_create - rather than when starting. that ensures it dies well before the receiver
            # Which is better for flushing TCP sockets
            kill_upon_create=True,
            cset='i_tcp',
            rtprio=46,
    )
    tcp_send.start_order = 2
    tcp_send.kill_order = 0

    '''
    utr_red = DependentProcess(
            tmux_name='apapane_utr',
            cli_cmd=
            'milk-exec "mload milkimageformat; readshmim apapane_raw; imgformat.cred_cds_utr ..procinfo 1; imgformat.cred_cds_utr ..triggermode 3; imgformat.cred_cds_utr ..loopcntMax -1; imgformat.cred_cds_utr apapane_raw apapane 37000"',
            cli_args=(),
            kill_upon_create=True,
            cset='i_utr',
            rtprio=45,
    )
    utr_red.start_order = 0
    utr_red.kill_order = 2
    '''

    # PIPE over ZMQ into the LAN until we find a better solution (receiver)
    zmq_recv = RemoteDependentProcess(
            tmux_name='apapane_zmq',
            cli_cmd='zmq_recv.py %s:%u %s',
            cli_args=(scxconf.IPLAN_AORTS, scxconf.ZMQPORT_APAPANE, 'apapane'),
            remote_host=f'scexao-op@{scxconf.IP_SC2}',
            kill_upon_create=False,
    )
    zmq_recv.start_order = 5
    zmq_recv.kill_order = 6

    # PIPE over ZMQ into the LAN until we find a better solution (sender)
    zmq_send = DependentProcess(
            tmux_name='apapane_zmq',
            cli_cmd='zmq_send.py %s:%u %s -f 100',
            cli_args=(scxconf.IPLAN_AORTS, scxconf.ZMQPORT_APAPANE, 'apapane'),
            kill_upon_create=True,
    )
    zmq_send.start_order = 6
    zmq_send.kill_order = 5

    cam = ApapaneAtAORTS('apapane', 'apapane', unit=0, channel=0, mode_id=mode,
                  taker_cset_prio=('i_edt', 48), dependent_processes=[
                          tcp_recv, tcp_send, zmq_recv, zmq_send
                  ])  #, tcp_send_raw, tcp_recv_raw])

    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())

    # PYROSERVER
    from scxconf import PYRONS3_HOST, PYRONS3_PORT, IP_AORTS_SUMMIT
    from camstack import pyro_keys as pk
    from swmain.network.pyroserver_registerable import PyroServer

    server = PyroServer(bindTo=(IP_AORTS_SUMMIT, 0),
                        nsAddress=(PYRONS3_HOST, PYRONS3_PORT))
    server.add_device(cam, pk.APAPANE, add_oneway_callables=True)
    server.start()
