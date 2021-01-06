#!/bin/env python

'''
    camstack server starter

    Will start the server tmux

    TODO: cpusets and RTprios - setuid on EDTtake ?
    TODO: Maintain docopt consistency between

    Usage:
        camstack.main [--server]
'''

# Who's who - static identifyers
from camstack.core.edtcamera import EDTCamera
from camstack.core.dummyCamera import DummyCamera
from camstack.cams.cred2 import CRED2
from camstack.cams.ocam import OCAM2K

CLASS_DICT = {
    'dummycam': DummyCamera,
    'chuck': CRED2,
    'rajni': CRED2,
    'reno': OCAM2K,
    'ocam': OCAM2K,
}