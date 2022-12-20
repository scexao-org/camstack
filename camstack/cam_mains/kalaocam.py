# Quick shorthand for testing

import sys

sys.path.insert(0, "/home/kalao/kalao-cacao/src/pyMilk")
sys.path.insert(0, "/home/kalao/kalao-camstack")

from camstack.core.utilities import DependentProcess, RemoteDependentProcess
from camstack.cams.nuvu import Kalao

#import scxconf

if __name__ == "__main__":

    # mode = 0 # 128x128
    mode = 1  # 64x64 binning

    cam = Kalao('nuvu', 'nuvu_raw', unit=0, channel=0, mode_id=mode)

    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())
