from typing import Tuple

class CameraMode:
    def init(*,
             x0: int = None,
             x1: int = None,
             y0: int = None,
             y1: int = None,
             fps: float = None,
             tint: float = None,
             binx: int = None,
             biny: int = None,
             fgsize: Tuple[int,int] = None):
        self.x0 = x0 # First COLUMN
        self.x1 = x1 # Last COLUMN (inclusive)
        self.y0 = y0 # First ROW
        self.y1 = y1 # Last ROW (inclusive)
        self.fps = fps
        self.tint = tint
        self.binx = binx # Future use ?
        self.biny = biny

        # fgsize: COLUMNS, then ROWS
        if self.fgsize is not None:
            self.fgsize = fgsize
        else:
            self.fgsize = (self.x1 - self.x0 + 1, self.y1 - self.y0 + 1)


class TmuxTalk:
    def __init__(name: str, ssh: str = None):
        '''
            Initialize a tmux session
            name: tmux name
            ssh: IP addr to ssh over, or None for a local session
        '''
        pass

    def is_alive(self):
        pass
        return is_alive

    def