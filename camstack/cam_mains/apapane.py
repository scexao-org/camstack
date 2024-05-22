import os

from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.cred1 import Apapane, CRED1
from camstack.cams.cred2 import ApapaneButItsGLINT, CRED2

from camstack.core.logger import init_camstack_logger

from scxkw.config import MAGIC_HW_STR

# PYROSERVER
import scxconf
import scxconf.pyrokeys as pk
from swmain.network.pyroserver_registerable import PyroServer

from camstack.core.utilities import shellify_methods
from argparse import ArgumentParser

parser = ArgumentParser(
        prog="apapanemain",
        description="Start apapane, with Apapane or GLINT as actual camera.")
parser.add_argument("camflag", choices=['A', 'G', 'AUTO'], type=str.upper,
                    help="Physical camera: A Apapane | G Glint | AUTO",
                    default='AUTO', nargs='?')


def main():
    args = parser.parse_args()
    cam_flag: str = args.camflag

    if cam_flag == 'AUTO':
        # Perform a direct call to obtain the hwuid of the camera.
        from hwmain.edt.edtinterface import EdtInterfaceSerial
        # This cfg file will work the serial for all FLI cameras.
        edt_serial = EdtInterfaceSerial(
                unit=1, channel=0, config_file=os.environ['HOME'] +
                '/src/camstack/config/cred2_single_channel.cfg')

        success = False
        for _ in range(3):
            try:
                uid = edt_serial.send_command(
                        'hwuid',
                        base_timeout=5.0).removesuffix('\r\nOK\r\nfli-cli>')

                cam_flag = {
                        '01-000016436d3e': 'G',
                        '01-0000190ddb96': 'A',
                        None: 'I'
                }[uid]
                success = True
            except Exception as exc:
                pass

        if not success:
            print('Serial buffer is probably borked.')
            raise exc

    os.makedirs(os.environ['HOME'] + "/logs", exist_ok=True)
    init_camstack_logger(os.environ['HOME'] + "/logs/camstack-apapane.log")

    type_lookup: dict[str, type[CRED1 | CRED2]] = {
            'A': Apapane,
            'G': ApapaneButItsGLINT,
    }

    Klass: type = type_lookup[cam_flag]
    mode = 3

    # Prepare dependent processes
    tcp_recv = RemoteDependentProcess(
            tmux_name=f'streamTCPreceive_{scxconf.TCPPORT_APAPANE}',
            # Urrrrrh this is getting messy
            cli_cmd=
            'creashmim %s %u %u --type=f32 --kw=300; shmimTCPreceive -c ircam '
            + f'{scxconf.TCPPORT_APAPANE}',
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
            'milk-exec "creashmim %s %u %u --type=u16 --kw=300"; shmimTCPreceive -c ircam '
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

    if cam_flag == 'A':
        utr_cmdline = (
                'milk-exec "mload milkimageformat;'
                'readshmim apapane_raw; imgformat.cred_cds_utr ..procinfo 1; '
                'imgformat.cred_cds_utr ..triggermode 3; '
                'imgformat.cred_cds_utr ..loopcntMax -1; '
                'imgformat.cred_cds_utr apapane_raw apapane 37000"')
    elif cam_flag == 'G':
        utr_cmdline = (
                'milk-exec "mload milkimageformat;'
                'readshmim apapane_raw; imgformat.cred_cds_utr ..procinfo 1; '
                'imgformat.cred_cds_utr ..triggermode 3; '
                'imgformat.cred_cds_utr ..loopcntMax -1; '
                'imgformat.cred_cds_utr apapane_raw apapane 37000"')

    utr_red = DependentProcess(
            tmux_name='apapane_utr',
            cli_cmd=utr_cmdline,
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
            remote_host=f'scexao@{scxconf.IP_SC2}',
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

    cam = Klass('apapane', 'apapane_raw', unit=1, channel=0, mode_id=mode,
                taker_cset_prio=('a_edt', 48), dependent_processes=[
                        tcp_recv, tcp_send, utr_red, zmq_recv, zmq_send
                ])  #, tcp_send_raw, tcp_recv_raw])

    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())

    server = PyroServer(bindTo=(scxconf.IP_SC5, 0),
                        nsAddress=(scxconf.PYRONS3_HOST, scxconf.PYRONS3_PORT))
    server.add_device(cam, pk.APAPANE, add_oneway_callables=True)
    server.start()

    return cam, server


if __name__ == "__main__":
    cam, server = main()
