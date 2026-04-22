# More technical info

The python stack for camera control is heavily object-oriented and a bit obfuscated.

This file outlines the inner workings of a camera initialization code. I'm taking the "Buffy" CRED1 as an example, which is nowhere close to the simplest, but outlines all the mechanisms involved.

## Subclassing layers

Generally, we can distinguish 4 layers in the class hierarchy of the cameras:
### The **base** layer
With only the class `BaseCamera`, that defines the general startup / teardown mechanisms but has a few abstract (fatal or non-fatal) methods.
### The **framegrabbing** layer
A subclass of *the base layer* that defines frame acquisition mechanisms for a given hardware method. If the *communication* method is gonna be unique for this *acquisition* method, this is also the layer in which it is defined, e.g. serial port communication through a given framegrabber.

### The **camera** layer.
A subclass of *the framegrabbing layer* that defines how a camera behaves and what it can do. Defines the subset of the specific commands this camera will take. Can it be configured per framerate, integration time, or both? What are the serial commands? Does it do NDR? What cropmodes should be configured? That sort of parameters.

### The **instance** layer.
A subclass of *the camera layer* that defines how **my precious** camera should behave. Water cooled or fans full blast? Give it a little nickname in the FITS keywords. Set a default cropmode/exposure time. And more! You have two identical cameras? Well this layer will be super thin and only define their name, so that very little duplication to do.

## Configuration flags

Each camera class contains a number of class-level flags that let us tune the behavior of the acquisition backend.
At every inheritance layer, you can expand (or override) the parameter from the superclass, e.g.

```python
class Superclass: # Base layer
    KEYWORDS = {'YOLO': 3.0}
    LISTSTUFF = [0]

class SubclassForFramegrabbing(Superclass): # Framegrabbing layer
    KEYWORDS = {'SWAG': 'I got some.'}
    KEYWORDS.update(Superclass.KEYWORDS)

    LISTSTUFF = Superclass.LISTSTUFF + [1,2,3]

    A_WEIRD_FLAG_FOR_THIS_FRAMEGRABBER_AND_SHOULD_BE_FALSE_BY_DEFAULT = False

class MyWeirdFramegrabbedCamera(SubclassForFramegrabbing): # Camera layer
    # This camera actually needs this weird flag (looking at you OCAM)
    A_WEIRD_FLAG_FOR_THIS_FRAMEGRABBER_AND_SHOULD_BE_FALSE_BY_DEFAULT = True

```

## The constructor process

I recommend you take a look a the main startup script for a camera instance, e.g. [here](camstack/cam_mains/kalaocam.py).

As you can see, we're importing a class all the way from the bottom of the class tree and creating an instance object. What happends then?


| BaseCamera layer                                 | FrameGrab layer                   | Camera Layer                     | Instance Layer          |
| ------------------------------------------------ | --------------------------------- | -------------------------------- | ----------------------- |
| (unique)                                         | (e.g. EDTCamera)                  | (e.g. CRED-1)                    | (e.g. Buffy)            |
|                                                  |                                   |                                  | Call `__init__`         |
|                                                  |                                   |                                  | Nothing to do           |
|                                                  |                                   | Call `__init__`                  | Call super().`__init__` |
|                                                  |                                   | Define CRED1-only flags          |                         |
|                                                  | call `__init__`                   | Call super().`__init__`          |                         |
|                                                  | Store framegrabber flags          |                                  |                         |
|                                                  | (board number, config file)       |                                  |                         |
| call `__init__`                                  | Call super().`__init__`           |                                  |                         |
| *Now we get serious*                             |                                   |                                  |                         |
| Conf. Camera modes (crop, fps, exp)              |                                   |                                  |                         |
| Conf. dependent process (Demangle, UTR, TCP)     |                                   |                                  |                         |
| Conf. polling thread (Fetch temperature, ...)    |                                   |                                  |                         |
| `self.kill_taker_and_dependents()`               |                                   |                                  |                         |
| (generally not subclassed. Ensures clean slate.) |                                   |                                  |                         |
| `self.init_framegrab_backend()`                  | *Call lands here*                 |                                  |                         |
|                                                  | Ensure **communication** is ready |                                  |                         |
| `self.prepare_camera_for_size()`                 |                                   | *Call lands here*                |                         |
|                                                  |                                   | (Requires comm. to camera)       |                         |
|                                                  |                                   | (The camera mode is defined)     |                         |
|                                                  |                                   | -> Camera ready to spit imgs     |                         |
|                                                  |                                   | (Quite variable with backend)    |                         |
| `self._start_taker_no_dependents()`              |                                   |                                  |                         |
| `---- self._prepare_backend_cmdline()`           | *Call lands here*                 |                                  |                         |
|                                                  | Prep. the bash line for acq.      |                                  |                         |
| Spin up acquistion in its tmux session           |                                   |                                  |                         |
| `---- self._ensure_backend_restarted()`          |                                   |                                  |                         |
| `---- self.grab_shm_fill_keywords()`             |                                   |                                  |                         |
| `---- self.prepare_camera_finalize()`            |                                   |                                  |                         |
| `---- self.start_auxiliary_thread()`             |                                   |                                  |                         |
|                                                  |                                   |                                  |                         |
|                                                  |                                   |                                  |                         |
|                                                  |                                   |                                  |                         |
|                                                  |                                   |                                  |                         |
|                                                  |                                   |                                  |                         |
|                                                  |                                   |                                  |                         |
|                                                  |                                   |                                  |                         |
|                                                  |                                   | Do some CRED1 final adjustments  |                         |
|                                                  |                                   | (`led off`, `rawimages on`, etc) |                         |

# THIS FILE WIP - TBC
