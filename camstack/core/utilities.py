from typing import Tuple


class CameraMode:
    def __init__(self,
                 *,
                 x0: int = None,
                 x1: int = None,
                 y0: int = None,
                 y1: int = None,
                 fps: float = None,
                 tint: float = None,
                 binx: int = 1,
                 biny: int = 1,
                 fgsize: Tuple[int, int] = None):

        self.x0 = x0  # First COLUMN
        self.x1 = x1  # Last COLUMN (inclusive)
        self.y0 = y0  # First ROW
        self.y1 = y1  # Last ROW (inclusive)
        self.fps = fps
        self.tint = tint
        self.binx = binx  # Future use ?
        self.biny = biny

        # fgsize: COLUMNS, then ROWS
        if fgsize is not None:
            self.fgsize = fgsize
        else:
            self.fgsize = (self.x1 - self.x0 + 1, self.y1 - self.y0 + 1)


class DependentProcess:
    '''
        Dependent processes are stuff that the camera server should take care of killing before changing the size
        and restarting after changing the size.
        
        They're expected to live in a tmux (local or remote)
        This typically will include ocamdecode, and the TCP transfer.
    '''

def shellify_methods(instance_of_camera, top_level_globals):
    '''
        
    '''
    for method_name in instance_of_camera.INTERACTIVE_SHELL_METHODS:
        top_level_globals[method_name] = getattr(instance_of_camera, method_name)
