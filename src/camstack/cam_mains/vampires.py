'''
    Usage:
        vampires.py

    Starts BOTH cameras.

'''
import os

from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.andors_autocamlink import Vampires

from camstack.core.logger import init_camstack_logger

from scxkw.config import MAGIC_HW_STR

import scxconf

if __name__ == "__main__":

    os.makedirs(os.environ['HOME'] + "/logs", exist_ok=True)
    init_camstack_logger(os.environ['HOME'] + "/logs/camstack-vampires.log")

    mode = 256

    kill_logshim_0 = RemoteDependentProcess(tmux_name='vcam_logcmd',
                                            cli_cmd="milk-logshimkill %s",
                                            cli_args=('vcamim0', ),
                                            remote_host=scxconf.IPLAN_SC6)
    kill_logshim_0.start_order = 0
    kill_logshim_0.stop_order = 0

    kill_logshim_1 = RemoteDependentProcess(tmux_name='vcam_logcmd',
                                            cli_cmd="milk-logshimkill %s",
                                            cli_args=('vcamim1', ),
                                            remote_host=scxconf.IPLAN_SC6)
    kill_logshim_1.start_order = 0
    kill_logshim_1.stop_order = 0

    # Prepare dependent processes - two TCPs and a logshim-killer.
    tcp_recv_0 = RemoteDependentProcess(
            tmux_name='streamTCPreceive_%u' % scxconf.TCPPORT_VCAM0,
            cli_cmd=
            f'milk-exec "creaushortimshm %s %u %u"; shmimTCPreceive -c aol0COM {scxconf.TCPPORT_VCAM0}',
            cli_args=('vcamim0', MAGIC_HW_STR.HEIGHT, MAGIC_HW_STR.WIDTH),
            remote_host=scxconf.IPLAN_SC6,
            kill_upon_create=False,
    )
    tcp_recv_0.start_order = 1
    tcp_recv_0.kill_order = 1

    tcp_recv_1 = RemoteDependentProcess(
            tmux_name='streamTCPreceive_%u' % scxconf.TCPPORT_VCAM1,
            cli_cmd=
            f'milk-exec "creaushortimshm %s %u %u"; shmimTCPreceive -c aol0COM {scxconf.TCPPORT_VCAM1}',
            cli_args=('vcamim1', MAGIC_HW_STR.HEIGHT, MAGIC_HW_STR.WIDTH),
            remote_host=scxconf.IPLAN_SC6,
            kill_upon_create=False,
    )
    tcp_recv_1.start_order = 1
    tcp_recv_1.kill_order = 1

    tcp_send_0 = DependentProcess(
            tmux_name='vcam0_tcp',
            cli_cmd='sleep 3; OMP_NUM_THREADS=1 shmimTCPtransmit %s %s %u',
            cli_args=('vcamim0', scxconf.IPP2P_SC6FROM5, scxconf.TCPPORT_VCAM0),
            kill_upon_create=True,
            cset='v_tcp',
            rtprio=45,
    )
    tcp_send_0.start_order = 2
    tcp_send_0.kill_order = 2

    tcp_send_1 = DependentProcess(
            tmux_name='vcam1_tcp',
            cli_cmd='sleep 3; OMP_NUM_THREADS=1 shmimTCPtransmit %s %s %u',
            cli_args=('vcamim1', scxconf.IPP2P_SC6FROM5, scxconf.TCPPORT_VCAM1),
            kill_upon_create=True,
            cset='v_tcp',
            rtprio=45,
    )
    tcp_send_1.start_order = 2
    tcp_send_1.kill_order = 2

    cam0 = Vampires(
            name='vcam0', stream_name='vcamim0', unit=2, channel=0,
            mode_id=mode, taker_cset_prio=('v0_asl', 45),
            dependent_processes=[tcp_recv_0, tcp_send_0, kill_logshim_0])
    cam1 = Vampires(
            name='vcam1', stream_name='vcamim1', unit=2, channel=1,
            mode_id=mode, taker_cset_prio=('v1_asl', 45),
            dependent_processes=[tcp_recv_1, tcp_send_1, kill_logshim_1])

    def release():
        cam0.release()
        cam1.release()

    def close():
        release()
