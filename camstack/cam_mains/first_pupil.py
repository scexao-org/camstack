import os

from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.flycapturecam import FirstPupilFlea

from camstack.core.logger import init_camstack_logger

if __name__ == "__main__":

    os.makedirs(os.environ['HOME'] + "/logs", exist_ok=True)
    init_camstack_logger(os.environ['HOME'] + "/logs/camstack-firstpupil.log")

    mode = FirstPupilFlea.FULL

    cam = FirstPupilFlea('fpup', 'fpupcam', mode_id=mode,
                         flycap_number=14317519, taker_cset_prio=('system',
                                                                  10),
                         dependent_processes=[])

    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())
