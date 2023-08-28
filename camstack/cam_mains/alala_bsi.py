import os

from camstack.cams.prime_bsi import JensPrimeBSI
from camstack.core.logger import init_camstack_logger

if __name__ == "__main__":

    os.makedirs(os.environ['HOME'] + "/logs", exist_ok=True)
    init_camstack_logger(os.environ['HOME'] + "/logs/camstack-primebsi.log")

    mode = JensPrimeBSI.FULL

    cam = JensPrimeBSI('jen', 'jen', pvcam_number=0, mode_id=mode,
                       taker_cset_prio=('user', 42), dependent_processes=[])

    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())
