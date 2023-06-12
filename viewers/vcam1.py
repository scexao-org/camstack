import click
from camstack.viewers.vampires.vcam import VAMPIRESBaseViewerBackend, VAMPIRESBaseViewerFrontend
from camstack.viewers.plugins import SaturationPlugin


@click.command("vcam1.py")
@click.option("-z", "--zoom", type=int, default=1,
              help="Graphics window zoom factor", show_default=True)
@click.option("-b", "--bin", "binn", type=int, default=1,
              help="SHM binning factor", show_default=True)
def main(zoom, binn):
    backend = VAMPIRESBaseViewerBackend(1, "vcam1")
    binned_backend_shape = (560 // binn, 560 // binn)

    frontend = VAMPIRESBaseViewerFrontend(1, zoom, 20, binned_backend_shape,
                                          fonts_zoom=2 * zoom)
    satplug = SaturationPlugin(frontend, sat_value=2**16, nonlin_value=6e4)
    frontend.plugins.append(satplug)
    frontend.register_backend(backend)
    backend.register_frontend(frontend)
    frontend.run()


if __name__ == "__main__":
    main()
