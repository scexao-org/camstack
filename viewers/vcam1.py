import click
from camstack.viewers.vampires.vcam import VAMPIRESBaseViewerBackend, VAMPIRESBaseViewerFrontend
from camstack.viewers.vampires.plugins import FilterWheelPlugin, MBIWheelPlugin, VAMPIRESPupilMode, FieldstopPlugin, VCAMDarkAcquirePlugin, VCAMTriggerPlugin, DiffFilterWheelPlugin, VCAMCompassPlugin, VCAMScalePlugin, DiffWheelBlockPlugin
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
                                          fonts_zoom=2 * zoom // binn)
    plugins = (
            SaturationPlugin(frontend, sat_value=65535,
                             textbox=frontend.lbl_saturation),
            FieldstopPlugin(frontend),
            FilterWheelPlugin(frontend),
            MBIWheelPlugin(frontend),
            VAMPIRESPupilMode(frontend),
            VCAMDarkAcquirePlugin(frontend, textbox=frontend.lbl_status),
            VCAMTriggerPlugin(frontend),
            DiffFilterWheelPlugin(frontend),
            VCAMCompassPlugin(
                    frontend,
                    imrpad_offset=41.323163723676146  # deg
            ),
            VCAMScalePlugin(frontend, platescale=6.018378804429752),
            DiffWheelBlockPlugin(frontend))

    frontend.plugins.extend(plugins)
    frontend.register_backend(backend)
    backend.register_frontend(frontend)
    frontend.run()


if __name__ == "__main__":
    main()
