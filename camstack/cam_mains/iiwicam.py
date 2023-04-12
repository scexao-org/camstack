import os

from camstack.core.utilities import DependentProcess
from camstack.cams.cred1 import Iiwi

from camstack.core.logger import init_camstack_logger

if __name__ == "__main__":

    os.makedirs(os.environ['HOME'] + "/logs", exist_ok=True)
    init_camstack_logger(os.environ['HOME'] + "/logs/camstack-iiwi.log")

    mode = 0

    utr_red = DependentProcess(
            tmux_name='iiwi_utr',
            cli_cmd=
            'milk-exec "mload milkimageformat; readshmim iiwi_raw; imgformat.cred_cds_utr ..procinfo 1; imgformat.cred_cds_utr ..triggermode 3; imgformat.cred_cds_utr ..loopcntMax -1; imgformat.cred_cds_utr iiwi_raw iiwi 37000"',
            cli_args=(),
            kill_upon_create=True,
            cset='irwfs_utr',
            rtprio=49,
    )
    utr_red.start_order = 0
    utr_red.kill_order = 0

    dependent_processes = [utr_red]

    cam = Iiwi('iiwi', 'iiwi_raw', unit=0, channel=0, mode_id=mode,
               taker_cset_prio=('irwfs_edt',
                                49), dependent_processes=dependent_processes)

    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())
