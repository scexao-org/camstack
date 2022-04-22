# Quick shorthand for testing
from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.dcamcam import OrcaQuest

import os

if __name__ == "__main__":

    mode = OrcaQuest.FIRST

    cam = OrcaQuest('orcam',
                       'orcam',
                       dcam_number=0,
                       mode_id=mode,
                       taker_cset_prio=('user', 42),
                       dependent_processes=[])

    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())
