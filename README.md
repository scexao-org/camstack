# Camstack


Camera management stuff. Including keywords and TCP streaming from the stream source.

Gets installed with `pip install -e .`

Look at the scripts/startOCAM to get an idea.
This creates the python control shell in ocam_ctrl.

Also includes the camera viewers - and their backups

-----


## Camera acquisition stack

### Layout

`./scripts` folder: bash launcher scripts. Cleanup of the `<cam>_ctrl` tmux, and eventually launch the python `camstack.cam_mains.<cam>` main script.

`./camstack/cam_mains` folder: camera launcher python scripts.
- Define auxiliary tasks:
  - a tmux session
  - a command line
  - a cpuset and a real-time priority
  - and a sequencing order in which to be started/killed relative to other aux tasks.
- Instantiate the camera. A camera class is:
  - a subclass of the `BaseCamera`
  - with a specialized backend (USB, framegrabber, underlying API...)
  - with model specific definitions (C-Red One, C-Red 2, Orca, etc...)
  - with camera specific definitions (special cropmodes for Chuck, GLINT, etc...)

### Camera startup

Instantiating the Camera class eventually results in the camera freerunning in a shared memory and all the auxiliary tasks being started.

The camera launcher `camstack.cam_mains.<cam>` script, which runs in the `<cam>_ctrl` tmux session, eventually drops to an interactive python prompt. **This is where you control the camera**. A clean quit is performed by issuing the `close()` command.

### Class hierarchy and init sequence:

This is the general outline of what happens during the Camera Class constructor.

- `kill_taker_and_dependents()`: Allocate and clear all tmux sessions for framegrabber and auxiliary tasks
- `init_framegrab_backend()`: [BACKEND SPECIFIC] initialize resources for acquisition on the receiving end. This can be opening a serial port, configuring the acquisition size, etc...
- `prepare_camera_for_size()`: [BACKEND AND CAMERA SPECIFIC] set the camera crop mode. Performs tasks that need the camera control channel open but that need to be done before the acquisition starts.
- `_start_taker_no_dependents()`:
  - `_prepare_backend_cmdline()`: [BACKEND SPECIFIC] prep the shell line to be run in the `<cam>_fgrab` tmux. This is a minimal chunk of C to make the camera freerun to a SHM.
  - Start said cmdline and begin acquisition.
  - Adjust real-time priority and cpuset
- `grab_shm_fill_keywords()`: [CAMERA SPECIFIC] get a python handle to the freshly created SHM (by the framegrabbing process), and proceed to populate FITS keywords specific to the camera. They'll propagate through TCP all the way to the logger. This is not backend specific, the access is done through pyMilk, but the exact keywords are camera specific.
- `prepare_camera_finalize()`: [CAMERA, BACKEND SPECIFIC] Finish configuring the camera for the acquisition mode you want, with those last commands having to / allowed to be issued after the camera freeruns. Such as setting fps, integration time, NDR, exttrig for some models.

### Changing camera "mode"

Changing "mode" really means changing crop size. The framegrabber has to be reconfigure, all SHMs re-instantiated with their new size, etc. Pretty much all steps above are called in the same order.
This is done without quitting at the `<cam>_ctrl` command prompt, by calling `set_camera_mode(some_predefined_mode_id)`.

For dumb cameras (acquisition channel but no control channel), the FG acquisition can be set to an arbitrary size dynamically by calling `set_camera_size(height, width)`.


### Recap


| Camera | What      | Class | Medium               | Bash entry          | Python entry     | Computer | Stream   | Raw stream   |
| ------ | --------- | ----- | -------------------- | ------------------- | ---------------- | -------- | -------- | ------------ |
| Buffy  | CRED1     | Buffy | Camlink              | `cam-buffystart`    | `buffycam.py`    | scexao5  | `kcam`   | `kcam_raw`   |
| Chuck  | CRED2     | Buffy | Camlink              | `cam-chuckstart`    | `chuckcam.py`    | scexao5  | `ircam0` | `ircam0_raw` |
| GLINT  | CRED2     | Buffy | Camlink              | `cam-glintstart`    | `glintcam.py`    | scexao5  | `glint`  |              |
| Rajni  | CRED2     | Buffy | Camlink              | `cam-rajnistart`    | `rajnicam.py`    | scexao5  | `rajni`  |              |
| Reno   | Ocam2K    | Buffy | Camlink              | `cam-ocamstart`     | `renocam.py`     | scexao5  | `ocam2d` | `ocam2krc`   |
| Alala  | OrcaQuest | Buffy | CoaxPress (x)or USB3 | `cam-alalacamstart` | `first_orcam.py` | alala    | `orcam`  |              |
| FIRST  | OrcaQuest | Buffy | CoaxPress (x)or USB3 | `cam-fircamstart`   | `alala_orcam.py` | first    | `orcam`  |              |


### Class tree:

- BaseCamera
  - EDTCamera
    - CRED1
      - Buffy
    - CRED2
      - Chuck
      - GLINT
      - Rajni
    - OCAM2K
    - Andor897 (unused / draft)
      - First
      - Vampires
  - DCAMCamera
    - OrcaQuest
      - FIRSTOrcam
      - AlalaOrcam