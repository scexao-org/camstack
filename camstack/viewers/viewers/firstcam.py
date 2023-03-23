import docopt

from camstack.viewers.generic_viewer_frontend import GenericViewerFrontend
from camstack.viewers.generic_viewer_backend import GenericViewerBackend

class FirstViewerBackend(GenericViewerBackend):
    pass

class FirstViewerFrontend(GenericViewerFrontend):
    WINDOW_NAME = 'FIRST camera'
    CARTOON_FILE = 'io.png'

    def __init__(self, system_zoom, fps, display_base_size):

        # Hack the arguments BEFORE
        GenericViewerFrontend.__init__(self, system_zoom, fps,
                                       display_base_size)

        # Finalize some specifics AFTER
#!/usr/bin/env python

DEFAULT_SHM_NAME = "orcam"

__doc__ = f'''
    FIRST Orcaquest viewer

    Usage:
        firstcam [<shm_name>] [-z <zoom>] [-b <binn>]
        firstcam (-h | --help)

    Arguments:
        shm_name:   Shared memory stream name [default: {DEFAULT_SHM_NAME}]

    Options:
        -h --help           Show this screen.
        -z <zoom>           Graphics windows factor [default: 1]
        -b <binn>           SHM binning factor [default: 1]
'''

def main():
    # parse arguments
    args = docopt.docopt(__doc__)
    zoom = int(args['-z'])
    shm_name = args['<shm_name>']
    if shm_name is None:
        shm_name = DEFAULT_SHM_NAME

    # setup viewer
    backend = FirstViewerBackend(shm_name)
    frontend = FirstViewerFrontend(zoom, 20, backend.shm_shape)
    frontend.register_backend(backend)
    # go
    frontend.run()

if __name__ == '__main__':
    main()
