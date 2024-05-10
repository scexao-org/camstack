import os

from scxkw.config import MAGIC_HW_STR

from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.vampires import VCAM1, VCAM2, BaseVCAM
from camstack.core.logger import init_camstack_logger

# PYROSERVER
import scxconf
import scxconf.pyrokeys as pk
from swmain.network.pyroserver_registerable import PyroServer
from camstack.core.utilities import shellify_methods
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument("cam", type=int, choices=(1, 2))
parser.add_argument("-m", "--mode", choices=list(VCAM1.MODES.keys()),
                    default=BaseVCAM.STANDARD,
                    help="Camera mode (default is %(default)s)")


def main():
    args = parser.parse_args()
    cam = args.cam
    mode = args.mode.upper()
    os.makedirs(os.environ["HOME"] + "/logs", exist_ok=True)
    init_camstack_logger(os.environ["HOME"] + f"/logs/camstack-vcam{cam}.log")

    stream_name = f'vcam{cam}'
    dark_stream_name = f'vcam{cam}_dark'
    cpuset_acquisition = f'v{cam}_asl'
    cpuset_tcp = f'v{cam}_tcp'
    if cam == 1:
        Klass = VCAM1
        TCP_PORT = scxconf.TCPPORT_VCAM1
        ZMQ_PORT = scxconf.ZMQPORT_VCAM1
        DARKZMQ_PORT = scxconf.ZMQPORT_VCAM1_DARK
        pyrokey = pk.VCAM1
    else:
        Klass = VCAM2
        TCP_PORT = scxconf.TCPPORT_VCAM2
        ZMQ_PORT = scxconf.ZMQPORT_VCAM2
        DARKZMQ_PORT = scxconf.ZMQPORT_VCAM2_DARK
        pyrokey = pk.VCAM2
    # special hack- if we're in FULL mode, do NOT stream TCP over LAN
    # because the orcas put out ~16 Gbps (this angers the LAN)
    if mode != BaseVCAM.FULL:
        # Prepare dependent processes
        tcp_recv = RemoteDependentProcess(
                tmux_name=f'streamTCPreceive_{TCP_PORT}',
                # Urrrrrh this is getting messy
                cli_cmd=
                'creashmim %s %u %u --type=u16 --kw=200; shmimTCPreceive -c aol0RT2 %s',
                cli_args=(stream_name, MAGIC_HW_STR.HEIGHT, MAGIC_HW_STR.WIDTH,
                          TCP_PORT),
                remote_host='scexao@' + scxconf.IPLAN_SC6,
                kill_upon_create=False,
        )
        tcp_recv.start_order = 0
        tcp_recv.kill_order = 1

        tcp_send = DependentProcess(
                tmux_name=f'vcam{cam}_tcp',
                cli_cmd='sleep 3; OMP_NUM_THREADS=1 shmimTCPtransmit %s %s %u',
                cli_args=(stream_name, scxconf.IPP2P_SC6FROM5, TCP_PORT),
                # Sender is kill_upon_create - rather than when starting. that ensures it dies well before the receiver
                # Which is better for flushing TCP sockets
                kill_upon_create=True,
                cset=cpuset_tcp,
                rtprio=45,
        )
        tcp_send.start_order = 1
        tcp_send.kill_order = 0

        ## SC5 -> VAMPIRES zmq
        # PIPE over ZMQ into the LAN until we find a better solution (receiver)
        zmq_recv = RemoteDependentProcess(
                tmux_name=f'vcam{cam}_zmq',
                cli_cmd='zmq_recv.py %s:%u %s',
                cli_args=(scxconf.IP_SC5, ZMQ_PORT, stream_name),
                remote_host=f'lestat@{scxconf.IP_VAMPIRES}',
                kill_upon_create=False,
        )
        zmq_recv.start_order = 2
        zmq_recv.kill_order = 3

        # PIPE over ZMQ into the LAN until we find a better solution (sender)
        zmq_send = DependentProcess(
                tmux_name=f'vcam{cam}_zmq',
                cli_cmd='zmq_send.py %s:%u %s -f 10',
                cli_args=(scxconf.IP_SC5, ZMQ_PORT, stream_name),
                kill_upon_create=True,
        )
        zmq_send.start_order = 3
        zmq_send.kill_order = 2

        ## DARKS SC5 -> VAMPIRES zmq
        # PIPE over ZMQ into the LAN until we find a better solution (receiver)
        darkzmq_recv_vampires = RemoteDependentProcess(
                tmux_name=f'vcam{cam}_dark_zmq',
                cli_cmd='zmq_recv.py %s:%u %s',
                cli_args=(scxconf.IP_SC5, DARKZMQ_PORT, dark_stream_name),
                remote_host=f'lestat@{scxconf.IP_VAMPIRES}',
                kill_upon_create=False,
        )
        darkzmq_recv_vampires.start_order = 4
        darkzmq_recv_vampires.kill_order = 6
        ## DARKS SC5 -> SC6
        # PIPE over ZMQ into the LAN until we find a better solution (receiver)
        darkzmq_recv_sc6 = RemoteDependentProcess(
                tmux_name=f'vcam{cam}_dark_zmq',
                cli_cmd='zmq_recv.py %s:%u %s',
                cli_args=(scxconf.IP_SC5, DARKZMQ_PORT, dark_stream_name),
                remote_host=f'scexao@{scxconf.IP_SC6}',
                kill_upon_create=False,
        )
        darkzmq_recv_sc6.start_order = 5
        darkzmq_recv_sc6.kill_order = 5

        # PIPE over ZMQ into the LAN until we find a better solution (sender)
        darkzmq_send = DependentProcess(
                tmux_name=f'vcam{cam}_dark_zmq',
                cli_cmd='zmq_send.py %s:%u %s -f 10',
                cli_args=(scxconf.IP_SC5, DARKZMQ_PORT, dark_stream_name),
                kill_upon_create=True,
        )
        darkzmq_send.start_order = 6
        darkzmq_send.kill_order = 4

    vcam = Klass(
            stream_name,
            stream_name,
            # for some reason -u 1 is vcam1 and -u 0 is vcam2
            dcam_number=cam % 2,
            mode_id=mode,
            taker_cset_prio=(cpuset_acquisition, 42),
            dependent_processes=[
                    #tcp_recv, tcp_send,
                    zmq_recv,
                    zmq_send,
                    darkzmq_recv_vampires,
                    darkzmq_recv_sc6,
                    darkzmq_send
            ],
    )
    shellify_methods(vcam, globals())
    globals()["cam"] = vcam

    # start pyro server - you don't need a static port allocation (0 is magic for autoport)
    # Only the NS needs to be always located.
    server = PyroServer(bindTo=(scxconf.IP_SC5, 0),
                        nsAddress=(scxconf.PYRONS3_HOST, scxconf.PYRONS3_PORT))
    server.add_device(vcam, pyrokey, add_oneway_callables=True)

    globals()["server"] = server
    server.start()


if __name__ == "__main__":
    main()
