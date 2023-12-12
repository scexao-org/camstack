#!/usr/bin/env python
'''
    pygame SHM viewer - generic basic version

    Usage:
        anycam.py <shm_name> [-z <zoom>] [-b <binn>] [-w] [--hack] [--nohack]

    Options:
        -z <zoom>    Graphics windows factor [default: 1]
        -w           Hidpi displays, forces fontzoom to 2.
        -b <binn>    SHM binning factor [default: 1]
'''

import docopt
import os

args = docopt.docopt(__doc__)

if args['--hack']:
    os.environ["GLHACK_FORCE"] = "1"
if args['--nohack']:
    os.environ["GLHACK_FORCENOT"] = "1"
# We use the environment to manipulate the libGL hack that's happening
# At the top of the import of generic_viewer_frontend
from camstack.viewertools.generic_viewer_frontend import GenericViewerFrontend
from camstack.viewertools.generic_viewer_backend import GenericViewerBackend

zoom = int(args['-z'])
binn = int(args['-b'])
shm_name = args['<shm_name>']

if args['-w']:
    fonts_zoom = 2 * zoom
else:
    fonts_zoom = None

backend = GenericViewerBackend(shm_name)

binned_backend_shape = (backend.shm_shape[0] // binn,
                        backend.shm_shape[1] // binn)

frontend = GenericViewerFrontend(zoom, 20, binned_backend_shape,
                                 fonts_zoom=fonts_zoom)
frontend.register_backend(backend)
frontend.run()  # Perpetual while True:


# For pyproject entrypoint.
def dud_main():
    pass
