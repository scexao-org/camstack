#!/usr/bin/env python
'''
    pygame SHM viewer - generic basic version

    Usage:
        anycam.py <shm_name> [-z <zoom>]

    Options:
        -z <zoom>    System zoom factor [default: 1]
'''

import docopt

from camstack.viewers.generic_viewer_frontend import GenericViewerFrontend
from camstack.viewers.generic_viewer_backend import GenericViewerBackend

if __name__ == '__main__':

    args = docopt.docopt(__doc__)
    zoom = int(args['-z'])
    shm_name = args['<shm_name>']

    backend = GenericViewerBackend(shm_name)

    frontend = GenericViewerFrontend(zoom, 20, backend.shm_shape)
    frontend.register_backend(backend)
    frontend.run()
