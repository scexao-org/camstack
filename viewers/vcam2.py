import click
from camstack.viewers.vampires.vcam import VAMPIRESBaseViewerBackend, VAMPIRESBaseViewerFrontend
from camstack.viewers.vampires.plugins import FilterWheelPlugin, MBIWheelPlugin, VAMPIRESPupilMode, FieldstopPlugin, VCAMDarkAcquirePlugin
from camstack.viewers.plugins import SaturationPlugin, CenteredCrossHairPlugin


@click.command("vcam2.py")
@click.option("-z", "--zoom", type=int, default=1,
              help="Graphics window zoom factor", show_default=True)
@click.option("-b", "--bin", "binn", type=int, default=1,
              help="SHM binning factor", show_default=True)
def main(zoom, binn):
    backend = VAMPIRESBaseViewerBackend(2, "vcam2")
    binned_backend_shape = (560 // binn, 560 // binn)

    frontend = VAMPIRESBaseViewerFrontend(2, zoom, 20, binned_backend_shape,
                                          fonts_zoom=2 * zoom)
    plugins = (SaturationPlugin(frontend, sat_value=65535,
                                textbox=frontend.lbl_saturation),
               FieldstopPlugin(frontend), FilterWheelPlugin(frontend),
               MBIWheelPlugin(frontend), VAMPIRESPupilMode(frontend),
               VCAMDarkAcquirePlugin(frontend, textbox=frontend.lbl_status))

    frontend.plugins.extend(plugins)
    frontend.register_backend(backend)
    backend.register_frontend(frontend)
    frontend.run()


if __name__ == "__main__":
    main()
