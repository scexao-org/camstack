# Quick shorthand for testing
from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.flycapturecam import FirstPupilFlea

import os

if __name__ == "__main__":

    mode = FirstPupilFlea.FULL

    cam = FirstPupilFlea('fpup', 'fpupcam', mode_id=mode,
                         flycap_number=14317519, taker_cset_prio=('system',
                                                                  10),
                         dependent_processes=[])

    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())
