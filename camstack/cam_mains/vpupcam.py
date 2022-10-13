from camstack.cams.flycapturecam import VampiresPupilFlea

DEFAULT_SHM_NAME = "vpupcam"

def main():
    # start running backend
    cam = VampiresPupilFlea("vpup", DEFAULT_SHM_NAME, "FULL", 0)


if __name__ == "__main__":
    main()