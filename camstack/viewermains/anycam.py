#!/usr/bin/env python
'''
    pygame SHM viewer - generic basic version

    Usage:
        anycam.py <shm_name> [-z <zoom>] [-b <binn>] [-w] [-f <fz>]

    Options:
        -z <zoom>    Graphics windows factor [default: 1]
        -f <fzoom>   Separate zooming for test. Default to == -z [default: 0]
        -w           Hidpi displays, forces fontzoom to 2 x <zoom>
        -b <binn>    SHM binning factor [default: 1]
'''

import docopt

args = docopt.docopt(__doc__)
from camstack.viewertools.pygame_viewer_frontend import PygameViewerFrontend
from camstack.viewertools.generic_viewer_backend import GenericViewerBackend

print(args)

zoom = int(args['-z'])

fonts_zoom = int(args['-f'])
if args['-w']:
    fonts_zoom = 2 * zoom
if fonts_zoom == 0:
    fonts_zoom = None

binn = int(args['-b'])

shm_name = args['<shm_name>']

backend = GenericViewerBackend(shm_name)

binned_backend_shape = (backend.shm_shape[0] // binn,
                        backend.shm_shape[1] // binn)
print(zoom, fonts_zoom)
frontend = PygameViewerFrontend(zoom, 20, binned_backend_shape,
                                fonts_zoom=fonts_zoom)
frontend.register_backend(backend)
frontend.run()  # Perpetual while True:


# For pyproject entrypoint.
def dud_main():
    pass
