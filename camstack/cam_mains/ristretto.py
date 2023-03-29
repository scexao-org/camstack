import os

#from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.cred1 import Ristretto

from camstack.core.logger import init_camstack_logger

if __name__ == "__main__":

    os.makedirs(os.environ['HOME'] + "/logs", exist_ok=True)

    init_camstack_logger(os.environ['HOME'] + "/logs/camstack-ristretto.log")

    mode = 99

    cam = Ristretto('ristretto', 'ristretto_raw', unit=0, channel=0,
                    mode_id=mode, dependent_processes=[])
    #, taker_cset_prio=('ristretto_edt', None))

    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())
