import os

from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.dcamcam import AlalaOrcam
from camstack.core.logger import init_camstack_logger

if __name__ == "__main__":

    os.makedirs(os.environ['HOME'] + "/logs", exist_ok=True)
    init_camstack_logger(os.environ['HOME'] + "/logs/camstack-milescam.log")

    #mode = AlalaOrcam.FULL
    mode = AlalaOrcam.DICHROIC

    cam = AlalaOrcam('miles', 'miles', dcam_number=1, mode_id=mode,
                     taker_cset_prio=('user', 42), dependent_processes=[])

    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())
