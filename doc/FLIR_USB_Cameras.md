# FLIR/Teledyne USB Cameras

For the many variants of FLIR USB cameras (Grasshopper, Flea, Blackfly...), proceed as such:

## Install capability

- Download and install the appropriate SDK from Teledyne [here](https://www.teledynevisionsolutions.com/fr-fr/categories/software/software-development-kits/).
  - Older cameras (Flea3, Grasshopper3) work with both the old FlyCapture SDK and the new Spinnaker SDK. My experience is that they're better behaved with FlyCapture, and this is what camstack supports.
  - New (e.g. BlackFly) require Spinnaker

- Use the main acquisition process from camstack to ensure the camera is detected and can acquire frames in default configuration:
  - FlyCapture: `python -m camstack.acq.flycapture_grab`
  - Spinnaker: `python -m camstack.acq.spinnaker_grab`
  - Spinnaker (more modern): `python -m camstack.acq.spinnaker_over_transport_grab`
Spinnaker / Flycapture will most likely require a venv to run. Calling the camstack session into the venv at launch can easily
be configured.

It it works, continue. If it doesn't, you'll need to troubleshoot at this step.
Add the `-B` flag to the command above to simply list cameras and confirm they're detected.

## Run as a camstack control server

Once sure the camera actually works, it can be run with a control server / acquisition backend process pair as all the others camstack cameras.

Control is performed from the control server. You need to fetch and instantiate the correct class, e.g.

```python
from camstack.cams.spinnakercam import BlackFlyS

cam = BlackFlyS('blackfly', 'blackfly', mode='FULL', spinnaker_number=0)
```

and that's it. Few control method are implemented for now: `get_tint`, `set_tint`, `get_fps`, `set_fps`, `set_camera_mode`, `set_camera_size`, etc. Which allow control of main acquisition parameters, all while the camera is freerunning into the SHM `blackfly`.

Note: we can easily expand the available functions by remapping more of Spinnakers capability.
