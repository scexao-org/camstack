import os

from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.edtcam import EDTCamera
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
parser.add_argument(
        "camflag", choices=['I', 'A', 'G', '5', 'AUTO'], type=str.upper, help=
        "Physical camera: I Iiwi | A Apapane | 5 Apapane on scexao5 | G Glint | AUTO (A,G,I)",
        default='AUTO', nargs='?')


def main():
    args = parser.parse_args()
    cam_flag: str = args.camflag

    if cam_flag == 'AUTO':
        # Perform a direct call to obtain the hwuid of the camera.
        from hwmain.edt.edtinterface import EdtInterfaceSerial
        # This cfg file will work the serial for all FLI cameras.
        edt_serial = EdtInterfaceSerial(
                unit=0, channel=0, config_file=os.environ['HOME'] +
                '/src/camstack/config/cred2_single_channel.cfg')
        uid = edt_serial.send_command(
                'hwuid', base_timeout=1.0).removesuffix('\r\nOK\r\nfli-cli>')

        cam_flag = {
                '01-000016436d3e': 'G',
                '01-0000190ddb96': 'A',
                None: 'I'
        }[uid]

    os.makedirs(os.environ['HOME'] + "/logs", exist_ok=True)
    init_camstack_logger(os.environ['HOME'] + "/logs/camstack-iiwi.log")

    type_lookup: dict[str, type[CRED1 | CRED2]] = {
            'I': Iiwi,
            'A': IiwiButItsApapane,
            '5': IiwiButItsApapane,
            'G': IiwiButItsGLINT,
    }

    Klass: type = type_lookup[cam_flag]
    mode = getattr(Klass, 'IIWI')

    if cam_flag in 'AGI':
        IPLAN_ACQSERVER = scxconf.IPLAN_AORTS
        IP_ACQSERVER = scxconf.IP_AORTS_SUMMIT
    else:
        # cam_flag == '5'
        IPLAN_ACQSERVER = scxconf.IPLAN_SC5
        IP_ACQSERVER = scxconf.IP_SC5

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
    dependent_processes: list[DependentProcess] = []
    stream_name = 'iiwi'

    # If this is the GLINT CRED2, we fire a downsampolator
    if cam_flag == 'G':
        stream_name = 'iiwi_raw'
        downsampler = DependentProcess(
                tmux_name='iiwi_160downsampler', cli_cmd=
                'python -i /home/aorts/src/camstack/scripts/iiwi_downsampler.py',
                cli_args=[], cset='i_acq_wfs', rtprio=45)
        downsampler.start_order = 0  # first
        downsampler.kill_order = 100  # last

        dependent_processes.append(downsampler)

    # PIPE over ZMQ into the LAN until we find a better solution (receiver)
    zmq_recv = RemoteDependentProcess(
            tmux_name='iiwi_zmq',
            cli_cmd='zmq_recv.py %s:%u %s',
            cli_args=(IPLAN_ACQSERVER, scxconf.ZMQPORT_IIWI, 'iiwi'),
            remote_host=f'scexao-op@{scxconf.IP_SC2}',
            kill_upon_create=False,
    )
    zmq_recv.start_order = 5
    zmq_recv.kill_order = 6

    # PIPE over ZMQ into the LAN until we find a better solution (sender)
    zmq_send = DependentProcess(
            tmux_name='iiwi_zmq',
            cli_cmd='zmq_send.py %s:%u %s -f 30',
            cli_args=(IPLAN_ACQSERVER, scxconf.ZMQPORT_IIWI, 'iiwi'),
            kill_upon_create=True,
    )
    zmq_send.start_order = 6
    zmq_send.kill_order = 5

    dependent_processes += [zmq_recv, zmq_send]

    if cam_flag == '5':
        # Add TCP streaming to RTS
        tcp_send = DependentProcess(
                tmux_name='iiwi_tcp',
                cli_cmd='sleep 3; OMP_NUM_THREADS=1 shmimTCPtransmit %s %s %u',
                cli_args=('iiwi', scxconf.IPLAN_AORTS, scxconf.TCPPORT_APAPANE),
                # Sender is kill_upon_create - rather than when starting. that ensures it dies well before the receiver
                # Which is better for flushing TCP sockets
                kill_upon_create=True,
                cset='a_tcp',
                rtprio=46,
        )
        tcp_send.start_order = 2
        tcp_send.kill_order = 0

        tcp_recv = RemoteDependentProcess(
                tmux_name=f'streamTCPreceive_{scxconf.TCPPORT_APAPANE}',
                # Urrrrrh this is getting messy
                cli_cmd=  # FIXME
                'milk-exec "creashmim %s %u %u --type=u16 --kw=300"; shmimTCPreceive -c i_edt '
                + f'{scxconf.TCPPORT_APAPANE}',
                cli_args=('iiwi', MAGIC_HW_STR.HEIGHT, MAGIC_HW_STR.WIDTH),
                remote_host=scxconf.IP_AORTS_SUMMIT,
                kill_upon_create=False,
        )
        tcp_recv.start_order = 1
        tcp_recv.kill_order = 1

    if cam_flag in 'AGI':
        cam = Klass('iiwi', stream_name, unit=0, channel=0, mode_id=mode,
                    taker_cset_prio=('i_edt', 48),
                    dependent_processes=dependent_processes)
    else:
        cam = Klass('iiwi', stream_name, unit=1, channel=0, mode_id=mode,
                    taker_cset_prio=('a_edt', 48),
                    dependent_processes=dependent_processes)

    shellify_methods(cam, globals())

    server = PyroServer(bindTo=(IP_ACQSERVER, 0),
                        nsAddress=(scxconf.PYRONS3_HOST, scxconf.PYRONS3_PORT))
    server.add_device(cam, pk.IIWI, add_oneway_callables=True)
    server.start()


if __name__ == "__main__":
    main()
