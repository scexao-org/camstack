#!/bin/env python

'''
    camstack server starter

    Ipython shell and main that start in the ctrl tmux

    TODO: cpusets and RTprios - setuid on EDTtake ?

    Usage:
        camstack.camstack_server_main <name> <unit> [-c <channel>] [-m <cam_mode>]
'''

from docopt import docopt
import libtmux as tmux

# Who's who - static identifyers
#from camstack.core.edtcamera import EDTCamera
from camstack.core.dummyCamera import DummyCamera
#from camstack.cams.cred2 import CRED2
#from camstack.cams.ocam import OCAM2K

CLASS_DICT = {
    'dummycam': DummyCamera,
    #'chuck': CRED2,
    #'rajni': CRED2,
    #'reno': OCAM2K,
    #'ocam': OCAM2K,
}

if __name__ == "__main__":
    args = docopt(__doc__)
    name = args['<name>']
    pdv_unit = int(args['<unit>'])
    if args['<channel>'] is None:
        pdv_channel = 0
    else:
        pdv_channel = int(args['<channel>'])
    if args['<channel>'] is None:
        inital_cropmode = args['<cam_mode>']
    else:
        inital_cropmode = 0

    Cam_Class = CLASS_DICT[name]

    cam = Cam_Class(name, pdv_unit, channel=pdv_channel)
    cam.set_camera_mode(0)
    cam.start_acquisition()