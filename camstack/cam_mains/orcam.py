# Quick shorthand for testing
from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.dcamcam import OrcaQuestUSB

import os

if __name__ == "__main__":

    mode = OrcaQuestUSB.FIRST

    cam = OrcaQuestUSB('orcam',
                       'orcam',
                       dcam_number=0,
                       mode_id=mode,
                       taker_cset_prio=('user', 42),
                       dependent_processes=[])

    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())
