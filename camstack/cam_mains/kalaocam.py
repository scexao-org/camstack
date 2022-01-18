# Quick shorthand for testing

import sys

sys.path.insert(0, "/home/kalao/kalao-cacao/src/pyMilk")
sys.path.insert(0, "/home/kalao/src/camstack")


from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.nuvu import Kalao

#import scxconf

if __name__ == "__main__":

    # mode = 0 # 128x128
    mode = 1 # 64x64 binning

    # Prepare dependent processes
    #tcp_recv = RemoteDependentProcess(
    #    tmux_name=f'streamTCPreceive_{scxconf.TCPPORT_RAJNI}',
    #    # Urrrrrh this is getting messy
    #    cli_cmd=
    #    'milk-exec "creasshortimshm %s %u %u"; shmimTCPreceive -c ircam ' +
    #    f'{scxconf.TCPPORT_RAJNI}',
    #    cli_args=('rajni', 320, 256),
    #    remote_host=scxconf.IP_SC6,
    #    kill_upon_create=False,
    #)
    #tcp_recv.start_order = 0
    #tcp_recv.kill_order = 1

    #tcp_send = DependentProcess(
    #    tmux_name='rajni_tcp',
    #    cli_cmd=
    #    'sleep 3; OMP_NUM_THREADS=1 shmimTCPtransmit %s %s %u',
    #    cli_args=('rajni', scxconf.IPP2P_SC6FROM5, scxconf.TCPPORT_RAJNI),
    #    # Sender is kill_upon_create - rather than when starting. that ensures it dies well before the receiver
    #    # Which is better for flushing TCP sockets
    #    kill_upon_create=True,
    #    cset='rajni_tcp',
    #    rtprio=40,
    #)
    #tcp_send.start_order = 1
    #tcp_send.kill_order = 0

    #utr_nuvu = DependentProcess(
    #    tmux_name='nuvu_utr',
    #    cli_cmd=
    #    'milk-exec "mload milkimageformat; readshmim nuvu_raw; imgformat.nuv_ql_utr ..procinfo 1; '
    #    'imgformat.nuv_ql_utr ..triggermode 3; imgformat.nuv_ql_utr ..loopcntMax -1; '
    #    'imgformat.nuv_ql_utr nuvu_raw nuvu 5000"',
    #    cli_args=(),
    #    kill_upon_create=True,
    #    cset='nuvu0_utr',
    #    rtprio=49,
    #)
    #utr_nuvu.start_order = 0
    #utr_nuvu.kill_order = 2


    cam = Kalao('nuvu',
                'nuvu_raw',
                unit=0,
                channel=0,
                mode_id=mode)

    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())
