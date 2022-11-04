#!/usr/bin/env python
'''
    pygame SHM viewer - generic basic version

    Usage:
        anycam.py <shm_name> [-z <zoom>] [-b <binn>]

    Options:
        -z <zoom>    Graphics windows factor [default: 1]
        -b <binn>    SHM binning factor [default: 1]
'''

import docopt

from camstack.viewers.generic_viewer_frontend import GenericViewerFrontend
from camstack.viewers.generic_viewer_backend import GenericViewerBackend

if __name__ == '__main__':

    args = docopt.docopt(__doc__)

    zoom = int(args['-z'])
    binn = int(args['-b'])
    shm_name = args['<shm_name>']

    backend = GenericViewerBackend(shm_name)

    binned_backend_shape = (backend.shm_shape[0] // binn,
                            backend.shm_shape[1] // binn)

    frontend = GenericViewerFrontend(zoom, 20, binned_backend_shape)
    frontend.register_backend(backend)
    frontend.run()
