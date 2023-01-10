#!/usr/bin/env python

DEFAULT_SHM_NAME = "vpupcam"
DEFAULT_PUPIL_CONFIG = ""

__doc__ = f"""
    VAMPIRES pupil viewer

    Usage:
        vpupcam [<shm_name>] [-z <zoom>] [-b <binn>] [-p | --preset <file>]
        vpupcam (-h | --help)

    Arguments:
        shm_name:   Shared memory stream name [default: {DEFAULT_SHM_NAME}]

    Options:
        -h --help           Show this screen.
        -z <zoom>           Graphics windows factor [default: 1]
        -b <binn>           SHM binning factor [default: 1]
        -p, --preset <file> Preset file used for pupil wheel positions [default: {DEFAULT_PUPIL_CONFIG}]
"""
from camstack.viewers.generic_viewer_frontend import GenericViewerFrontend
from camstack.viewers.generic_viewer_backend import GenericViewerBackend
import docopt

# from vampires_control.devices import pupil_wheel


help_msg = """VPUPCAM controls
---------------
h           : display this message
ESC         : quit vpupcam

camera controls:
----------------
q           : increase exposure time
a           : decrease exposure time
CTRL+o      : increase frame rate
CTRL+l      : decrease frame rate

desplay controls:
-----------------
l           : linear/non-linear display
c           : [TODO] estimate pupil position

pupil wheel controls:
---------------------
CTRL+1-- :  change filter wheel slot
        1:  EmptySlot
        2:  7hole
        3:  9hole
        4:  18hole
        5:  18holeNudged
        6:  AnnulusNudged
        7:  Mirror
        8:  OldAnnulus
        9:  LyotStop
        0:  EmptySlot2
        -:  Annulus_Ref
CTRL+ARROW:  Nudge wheel in y (left/right) and y (up/down)
CTRL+SHIFT+LEFT/RIGHT:  Rotate wheel CCW (left; angle increase) or CW (right; angle decrease)
CTRL+S:  Save current position to preset
CTRL+F:  Change preset file
"""


def main():
    args = docopt.docopt(__doc__)
    zoom = int(args["-z"])
    binn = int(args["-b"])
    if args["<shm_name>"]:
        shm_name = args["<shm_name>"]
    else:
        shm_name = DEFAULT_SHM_NAME


    backend = GenericViewerBackend(shm_name)

    binned_backend_shape = (backend.shm_shape[0] // binn, backend.shm_shape[1] // binn)

    frontend = GenericViewerFrontend(zoom, 20, binned_backend_shape)
    frontend.register_backend(backend)
    frontend.run()


if __name__ == "__main__":
    main()