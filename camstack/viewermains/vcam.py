import click

from camstack.viewerclasses.vcam import VAMPIRESBaseViewerBackend, VAMPIRESBaseViewerFrontend
from camstack.viewertools.plugins import SaturationPlugin
import camstack.viewertools.vampires_plugins as vplugs


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
            vplugs.FieldstopPlugin(frontend),
            vplugs.FilterWheelPlugin(frontend),
            vplugs.MBIWheelPlugin(frontend),
            vplugs.VAMPIRESPupilMode(frontend),
            vplugs.VCAMDarkAcquirePlugin(frontend, textbox=frontend.lbl_status),
            vplugs.VCAMTriggerPlugin(frontend),
            vplugs.DiffFilterWheelPlugin(frontend),
            vplugs.VCAMCompassPlugin(
                    frontend,
                    imrpad_offset=41.323163723676146  # deg
            ),
            vplugs.VCAMScalePlugin(frontend, platescale=6.018378804429752),
            vplugs.DiffWheelBlockPlugin(frontend))

    frontend.plugins.extend(plugins)
    frontend.register_backend(backend)
    backend.register_frontend(frontend)
    frontend.run()


@click.command("vcam2.py")
@click.option("-z", "--zoom", type=int, default=1,
              help="Graphics window zoom factor", show_default=True)
@click.option("-b", "--bin", "binn", type=int, default=1,
              help="SHM binning factor", show_default=True)
def main2(zoom, binn):
    backend = VAMPIRESBaseViewerBackend(2, "vcam2")
    binned_backend_shape = (560 // binn, 560 // binn)

    frontend = VAMPIRESBaseViewerFrontend(2, zoom, 20, binned_backend_shape,
                                          fonts_zoom=2 * zoom)
    plugins = (SaturationPlugin(frontend, sat_value=65535,
                                textbox=frontend.lbl_saturation),
               vplugs.FieldstopPlugin(frontend),
               vplugs.FilterWheelPlugin(frontend),
               vplugs.MBIWheelPlugin(frontend),
               vplugs.VAMPIRESPupilMode(frontend),
               vplugs.VCAMDarkAcquirePlugin(frontend,
                                            textbox=frontend.lbl_status),
               vplugs.VCAMTriggerPlugin(frontend),
               vplugs.DiffFilterWheelPlugin(frontend),
               vplugs.VCAMCompassPlugin(frontend,
                                        imrpad_offset=41.323163723676146),
               vplugs.VCAMScalePlugin(frontend, platescale=6.018378804429752),
               vplugs.DiffWheelBlockPlugin(frontend))

    frontend.plugins.extend(plugins)
    frontend.register_backend(backend)
    backend.register_frontend(frontend)
    frontend.run()
