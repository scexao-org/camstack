import click
from camstack.viewers.vampires.base import VAMPIRESBaseViewerBackend, VAMPIRESBaseViewerFrontend


class VAMPIRESCam1ViewerFrontend(VAMPIRESBaseViewerFrontend):
    WINDOW_NAME = "VCAM1"


class VAMPIRESCam1ViewerBackend(VAMPIRESBaseViewerBackend):
    pass


class VAMPIRESCam2ViewerFrontend(VAMPIRESBaseViewerFrontend):
    WINDOW_NAME = "VCAM2"


class VAMPIRESCam2ViewerBackend(VAMPIRESBaseViewerBackend):
    pass


@click.command("vcam1.py")
@click.option("-z", "--zoom", type=int, default=1,
              help="Graphics window zoom factor", show_default=True)
@click.option("-b", "--bin", "binn", type=int, default=1,
              help="SHM binning factor", show_default=True)
def launch_vcam1(zoom, binn):
    backend = VAMPIRESCam1ViewerBackend("vcam1")
    binned_backend_shape = (backend.shm_shape[0] // binn,
                            backend.shm_shape[1] // binn)

    frontend = VAMPIRESCam1ViewerFrontend(zoom, 20, binned_backend_shape,
                                          fonts_zoom=zoom)
    frontend.register_backend(backend)
    backend.register_frontend(frontend)
    frontend.run()


@click.command("vcam2.py")
@click.option("-z", "--zoom", type=int, default=1,
              help="Graphics window zoom factor", show_default=True)
@click.option("-b", "--bin", "binn", type=int, default=1,
              help="SHM binning factor", show_default=True)
def launch_vcam2(zoom, binn):
    backend = VAMPIRESCam2ViewerBackend("vcam2")
    binned_backend_shape = (backend.shm_shape[0] // binn,
                            backend.shm_shape[1] // binn)

    frontend = VAMPIRESCam2ViewerFrontend(zoom, 20, binned_backend_shape,
                                          fonts_zoom=zoom)
    frontend.register_backend(backend)
    backend.register_frontend(frontend)
    frontend.run()
