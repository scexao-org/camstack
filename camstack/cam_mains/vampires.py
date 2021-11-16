# Quick shorthand for testing
'''
    Usage:
        vampires.py <cam_number>

    
'''

from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.andors import Vampires

import scxconf

if __name__ == "__main__":

    from docopt import docopt
    args = docopt(__doc__)

    camnum = int(args['<cam_number>'])

    mode = 256

    # Prepare dependent processes
    port = {0: scxconf.TCPPORT_VCAM0, 1: scxconf.TCPPORT_VCAM1}[camnum]

    tcp_recv = RemoteDependentProcess(
        tmux_name='streamTCPreceive_%u' % port,
        # Urrrrrh this is getting messy
        cli_cmd=
        f'milk-exec "creaushortimshm %s %u %u"; shmimTCPreceive -c ircam {port}',
        cli_args=('vcamim%u' % camnum, 256, 256),
        remote_host=scxconf.IPLAN_SC6,
        kill_upon_create=False,
    )
    tcp_recv.start_order = 0
    tcp_recv.kill_order = 0

    tcp_send = DependentProcess(
        tmux_name='vcam%u_tcp' % camnum,
        cli_cmd=
        'sleep 3; OMP_NUM_THREADS=1 /home/scexao/bin/shmimTCPtransmit %s %s %u',
        cli_args=('vcamim%u' % camnum, scxconf.IPP2P_SC6FROM5, port),
        kill_upon_create=False,
        cset='vcam_tcp',
        rtprio=49,
    )
    tcp_send.start_order = 1
    tcp_send.kill_order = 1

    cam = Vampires('vcam%u' % camnum,
                   'vcamim%u' % camnum,
                   unit=2,
                   channel=camnum,
                   mode_id=mode,
                   taker_cset_prio=('vcam_edt', 49),
                   dependent_processes=[tcp_recv, tcp_send])

    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())