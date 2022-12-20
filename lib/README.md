# The libGL.so.1 hack.

pyMilk uses SDL to make the windows. Somewhere in the depth of that, it seems to call openGL for rendering.

This is the cause of many problems with X Forwarding due to the integration with X, OpenGL, GPU drivers, etc.

I note we have a different behavior in particular if we try X forwarding from/to a machine that has/hasn't nvidia GPUs/drivers installed.
Best case, errors like that:
```
X Error of failed request:  BadRequest (invalid request code or no such operation)
  Major opcode of failed request:  130 (MIT-SHM)
  Minor opcode of failed request:  1 (X_ShmAttach)
  Serial number of failed request:  200
  Current serial number in output stream:  201
```

Worst case, it nukes the client machines X display.



I found a way to circumvent that by getting the libGL.so.1 from Mesa, which is the one that machines that don't have nvidia should have.

Then, there's a hack at the top of genericViewerFrontend that allows dynamically modifying the LD_LIBRARY_PATH so that this libGL is loaded and not the system one.
Explicitly loading the .so with ctypes puts it in the python cache, and eventually calls from the depth of pygame to re-import it just grab this one.

-- Checks (in-progress) --
| What                                          | Works?                         |
| --------------------------------------------- | ------------------------------ |
| Local desktop - nvidia   (laptop)             | NO                             |
| Local desktop - nvidia   (VNC sc6)            | YES                            |
| Local desktop - no nvidia (VNC sc2 old 14.04) | YES                            |
| Local desktop - no nvidia (VNC sc5 20.04)     | YES                            |
| X forw. sc6 (NV) -> sc2 (noNV)                | YES                            |
| X forw. sc5 (noNV) -> sc2 (noNV)              | NO - opens but on wrong VNC??? |
| X forw. sc6 (NV) -> laptop (NV)               | YES                            |
| X forw. sc5 (noNV) -> laptop (NV)             | YES                            |
| X forw. sc2 (noNV) -> laptop (NV)             | YES                            |
