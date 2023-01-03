from camstack.cams.flycapturecam import VampiresPupilFlea

from camstack.core.utilities import shellify_methods

DEFAULT_SHM_NAME = "vpupcam"

if __name__ == "__main__":
    cam = VampiresPupilFlea("vpup", DEFAULT_SHM_NAME, "CROP_VPUP", 0)

    from camstack.core.utilities import shellify_methods
    shellify_methods(cam, globals())