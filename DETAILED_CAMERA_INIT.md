# Detailed initialization example

The python stack for camera control is heavily object-oriented and a bit obfuscated.

This file outlines the inner workings of a camera initialization code. I'm taking the "Buffy" CRED1 as an example, which is nowhere close to the simplest, but outlines all the mechanisms involved.

## Configuration flags

Each camera class contains a number of class-level flags that let us tune the behavior of the acquisition backend.

- `INTERACTIVE_SHELL_METHODS` is always a list of values that are promoted to be callable at the top level in the interpreter. I.e. once the `cam` object is created, this allows to call `set_gain()` at the python prompt instead of `cam.set_gain()`.
- `MODES`: All cameras have a list of `MODES` that defined pre-set bin, crop, exptime, fps modes to toggle between quickly.
- `KEYWORDS` is a key-value dictionary that is expanded with specifics as we get down into the subclasses. It defines all keywords that are carried around in the data stream. In the Subaru/SCExAO environment these keywords eventually make their way to FITS files and to the SCExAO status database.
- Some others, such as `EDTTAKE_UNSIGNED`, that configure the framegrabber flags (in this case, is the acquisition int16 or uint16) for a given camera class.

## This file is WIP
