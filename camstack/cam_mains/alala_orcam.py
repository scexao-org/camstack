# Quick shorthand for testing
from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.dcamcam import AlalaOrcam

import os

if __name__ == "__main__":

    mode = AlalaOrcam.FULL

    cam = AlalaOrcam('orcam',
                       'orcam',
                       dcam_number=0,
                       mode_id=mode,
                       taker_cset_prio=('user', 42),
                       dependent_processes=[])

    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())
