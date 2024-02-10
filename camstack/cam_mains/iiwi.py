import os

from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.cred1 import IiwiButItsApapane, Iiwi, CRED1
from camstack.cams.cred2 import IiwiButItsGLINT, CRED2

from camstack.core.logger import init_camstack_logger

from scxkw.config import MAGIC_HW_STR

# PYROSERVER
import scxconf
import scxconf.pyrokeys as pk
from swmain.network.pyroserver_registerable import PyroServer

from camstack.core.utilities import shellify_methods
from argparse import ArgumentParser

parser = ArgumentParser(
        prog="iiwimain",
        description="Start iiwi, with Iiwi, Apapane or GLINT as actual camera.")
parser.add_argument("camflag", choices=['I', 'A', 'G'], type=str.upper,
                    help="Physical camera: I Iiwi | A Apapane | G Glint",
                    default='I')


def main():
    args = parser.parse_args()
    cam_flag: str = args.camflag

    os.makedirs(os.environ['HOME'] + "/logs", exist_ok=True)
    init_camstack_logger(os.environ['HOME'] + "/logs/camstack-iiwi.log")

    type_lookup: dict[str, type[CRED1 | CRED2]] = {
            'I': Iiwi,
            'A': IiwiButItsApapane,
            'G': IiwiButItsGLINT,
    }

    Klass: type = type_lookup[cam_flag]
    mode = getattr(Klass, 'IIWI')

    # Prepare dependent processes
    '''
    # TODO - WHAT SHOULD WE DO WITH TCP AND LOGGING...
    tcp_recv = RemoteDependentProcess(
            tmux_name=f'streamTCPreceive_{scxconf.TCPPORT_APAPANE}',
            # Urrrrrh this is getting messy
            cli_cmd='shmimTCPreceive -c ircam ' + f'{scxconf.TCPPORT_APAPANE}',
            cli_args=(),
            remote_host=scxconf.IP_SC6,
            kill_upon_create=False,
    )
    tcp_recv.start_order = 1
    tcp_recv.kill_order = 1

    tcp_send = DependentProcess(
            tmux_name='apapane_tcp',
            cli_cmd='sleep 3; OMP_NUM_THREADS=1 shmimTCPtransmit %s %s %u',
            cli_args=('apapane', scxconf.IPLAN_SC6, scxconf.TCPPORT_APAPANE),
            # Sender is kill_upon_create - rather than when starting. that ensures it dies well before the receiver
            # Which is better for flushing TCP sockets
            kill_upon_create=True,
            cset='i_tcp',
            rtprio=46,
    )
    tcp_send.start_order = 2
    tcp_send.kill_order = 0
    '''

    # PIPE over ZMQ into the LAN until we find a better solution (receiver)
    zmq_recv = RemoteDependentProcess(
            tmux_name='iiwi_zmq',
            cli_cmd='zmq_recv.py %s:%u %s',
            cli_args=(scxconf.IPLAN_AORTS, scxconf.ZMQPORT_IIWI, 'iiwi'),
            remote_host=f'scexao-op@{scxconf.IP_SC2}',
            kill_upon_create=False,
    )
    zmq_recv.start_order = 5
    zmq_recv.kill_order = 6

    # PIPE over ZMQ into the LAN until we find a better solution (sender)
    zmq_send = DependentProcess(
            tmux_name='iiwi_zmq',
            cli_cmd='zmq_send.py %s:%u %s -f 100',
            cli_args=(scxconf.IPLAN_AORTS, scxconf.ZMQPORT_IIWI, 'iiwi'),
            kill_upon_create=True,
    )
    zmq_send.start_order = 6
    zmq_send.kill_order = 5

    cam = Klass('iiwi', 'iiwi', unit=0, channel=0, mode_id=mode,
                taker_cset_prio=('i_edt',
                                 48), dependent_processes=[zmq_recv, zmq_send])

    shellify_methods(cam, globals())

    server = PyroServer(bindTo=(scxconf.IP_AORTS_SUMMIT, 0),
                        nsAddress=(scxconf.PYRONS3_HOST, scxconf.PYRONS3_PORT))
    server.add_device(cam, pk.IIWI, add_oneway_callables=True)
    server.start()


if __name__ == "__main__":
    main()
