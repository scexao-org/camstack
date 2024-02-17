import os

from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.cred2 import GLINT
from camstack.core.logger import init_camstack_logger
import logging

import scxconf
from scxkw.config import MAGIC_HW_STR

from serial import Serial

if __name__ == "__main__":

    os.makedirs(os.environ['HOME'] + "/logs", exist_ok=True)
    init_camstack_logger(os.environ['HOME'] + "/logs/camstack-glint.log")

    ## Init the Kaya boxes
    logg = logging.warning('Resetting KAYA box over serial')

    KAYA_DEV = "/dev/serial/by-id/usb-Silicon_Labs_CP2101_USB_to_UART_Bridge_Controller_0001-if00-port0"
    assert os.path.exists(KAYA_DEV), "Kaya serial port seems to be absent."

    with Serial(KAYA_DEV, 115200, timeout=0.5) as kaya_ser:
        kaya_ser.write(b'FORMAT 3 1\r')
        kaya_ser.write(b'UARTBAUD 0 4\r')
        kaya_ser.write(b'FORMAT 3 1\r')
        kaya_ser.write(b'UARTBAUD 0 4\r')
    #os.system('stty -F ${DEV} 115200 raw -echo -echoe -echok -echoctl -echoke')

    mode = 12  #12

    # Prepare dependent processes
    tcp_recv = RemoteDependentProcess(
            tmux_name=f'streamTCPreceive_{scxconf.TCPPORT_GLINT}',
            # Urrrrrh this is getting messy
            cli_cmd=
            'milk-exec "creasshortimshm %s %u %u"; shmimTCPreceive -c ircam ' +
            f'{scxconf.TCPPORT_GLINT}',
            cli_args=('glint', MAGIC_HW_STR.HEIGHT, MAGIC_HW_STR.WIDTH),
            remote_host=scxconf.IP_SC6,
            kill_upon_create=False,
    )
    tcp_recv.start_order = 0
    tcp_recv.kill_order = 1

    tcp_send = DependentProcess(
            tmux_name='glint_tcp',
            cli_cmd='sleep 3; OMP_NUM_THREADS=1 shmimTCPtransmit %s %s %u',
            cli_args=('glint', scxconf.IPP2P_SC6FROM5, scxconf.TCPPORT_GLINT),
            # Sender is kill_upon_create - rather than when starting. that ensures it dies well before the receiver
            # Which is better for flushing TCP sockets
            kill_upon_create=True,
            cset='g_work',
            rtprio=44,
    )
    tcp_send.start_order = 1
    tcp_send.kill_order = 0

    try:
        os.makedirs(os.environ['MILK_SHM_DIR'] + '/smb')  # Samba server root
    except FileExistsError:
        pass

    fits_dump = DependentProcess(
            tmux_name='glint_fits',
            cli_cmd='OMP_NUM_THREADS=1 shmim2rollingFits %s %s %f glint_fits',
            cli_args=('glint', os.environ['MILK_SHM_DIR'] + "/smb/", 0.03),
            kill_upon_create=False,
    )
    fits_dump.start_order = 2
    fits_dump.kill_order = 2

    # PIPE over ZMQ into the LAN until we find a better solution (receiver)
    zmq_recv = RemoteDependentProcess(
            tmux_name='glint_zmq',
            cli_cmd='zmq_recv.py %s:%u %s',
            cli_args=(scxconf.IPLAN_SC5, scxconf.ZMQPORT_GLINT, 'glint'),
            remote_host=f'scexao-op@{scxconf.IP_SC2}',
            kill_upon_create=False,
    )
    zmq_recv.start_order = 3
    zmq_recv.kill_order = 4

    # PIPE over ZMQ into the LAN until we find a better solution (sender)
    zmq_send = DependentProcess(
            tmux_name='glint_zmq',
            cli_cmd='zmq_send.py %s:%u %s -f 100',
            cli_args=(scxconf.IPLAN_SC5, scxconf.ZMQPORT_GLINT, 'glint'),
            kill_upon_create=True,
    )
    zmq_send.start_order = 4
    zmq_send.kill_order = 3

    cam = GLINT(
            'glint',
            'glint',
            unit=4,
            channel=0,
            mode_id=mode,
            taker_cset_prio=('g_work', 45),
            dependent_processes=[
                    tcp_recv,
                    tcp_send,
                    #fits_dump,
                    zmq_recv,
                    zmq_send
            ])

    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())

    # PYROSERVER
    from scxconf import PYRONS3_HOST, PYRONS3_PORT, IP_SC5
    from camstack import pyro_keys as pk
    from swmain.network.pyroserver_registerable import PyroServer

    server = PyroServer(bindTo=(IP_SC5, 0),
                        nsAddress=(PYRONS3_HOST, PYRONS3_PORT))
    server.add_device(cam, pk.GLINT, add_oneway_callables=True)
    server.start()
