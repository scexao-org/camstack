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
from camstack.viewers.vampires import VAMPIRESPupilCamViewerBackend, VAMPIRESPupilCamViewerFrontend
from camstack.viewers.vampires.plugins import MaskWheelPlugin
import docopt


def main():
    args = docopt.docopt(__doc__)
    zoom = int(args["-z"])
    binn = int(args["-b"])
    if args["<shm_name>"]:
        shm_name = args["<shm_name>"]
    else:
        shm_name = DEFAULT_SHM_NAME

    backend = VAMPIRESPupilCamViewerBackend(shm_name)
    binned_backend_shape = (backend.shm_shape[0] // binn,
                            backend.shm_shape[1] // binn)

    frontend = VAMPIRESPupilCamViewerFrontend(zoom, 20, binned_backend_shape,
                                              fonts_zoom=2 * zoom)
    frontend.plugins.append(MaskWheelPlugin(frontend))
    frontend.register_backend(backend)
    backend.register_frontend(frontend)
    frontend.run()


if __name__ == "__main__":
    main()
