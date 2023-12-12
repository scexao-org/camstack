# Quick shorthand for testing

import os, sys

from camstack.core.logger import init_camstack_logger

sys.path.insert(0, "/home/kalao/kalao-cacao/src/pyMilk")
sys.path.insert(0, "/home/kalao/kalao-camstack")

from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.nuvu import Kalao

#import scxconf

if __name__ == "__main__":

    os.makedirs(os.environ['HOME'] + "/logs", exist_ok=True)

    init_camstack_logger(os.environ['HOME'] + "/logs/camstack-nuvu.log")

    # mode = 0 # 128x128
    mode = 1  # 64x64 binning

    cam = Kalao('nuvu', 'nuvu_raw', unit=0, channel=0, mode_id=mode,
                taker_cset_prio=('nuvu_cpuset', 44))

    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())
