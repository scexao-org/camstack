from typing import Tuple, List
from camstack.core import tmux
import time


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
    def __init__(self,
                 tmux_name: str,
                 cli_cmd: str,
                 cli_args: List[str],
                 cset: str = None,
                 rtprio: int = None,
                 kill_upon_create: bool = True):

        self.enabled = True  # Is this registered to run ? #TODO UNUSED

        self.tmux_name = tmux_name
        self.cli_cmd = cli_cmd
        self.cli_args = cli_args

        self.start_order = 0
        self.kill_order = 0

        self.initialize_tmux(kill_upon_create)

    def initialize_tmux(self, kill_upon_create):
        self.tmux_pane = tmux.find_or_create(self.tmux_name)
        if kill_upon_create:
            tmux.kill_running(self.tmux_pane)

    def start(self):
        tmux.send_keys(self.tmux_pane, self.cli_cmd % self.cli_args)
        time.sleep(1)

    def stop(self):
        tmux.kill_running(self.tmux_pane)
        time.sleep(1)

    def is_running(self):
        return self.get_pid() is not None

    def get_pid(self):
        return tmux.find_pane_running_pid(self.tmux_pane)


class RemoteDependentProcess(DependentProcess):
    def __init__(self,
                 tmux_name,
                 cli_cmd,
                 cli_args,
                 remote_host,
                 cset: str = None,
                 rtprio: int = None,
                 kill_upon_create: bool = True):

        self.remote_host = remote_host

        DependentProcess.__init__(self,
                                  tmux_name,
                                  cli_cmd,
                                  cli_args,
                                  cset=cset,
                                  rtprio=rtprio,
                                  kill_upon_create=kill_upon_create)

    def initialize_tmux(self, kill_upon_create):

        self.tmux_pane = tmux.find_or_create_remote(self.tmux_name,
                                                    self.remote_host)
        if kill_upon_create:
            tmux.kill_running(self.tmux_pane)


def shellify_methods(instance_of_camera, top_level_globals):
    '''
        
    '''
    for method_name in instance_of_camera.INTERACTIVE_SHELL_METHODS:
        top_level_globals[method_name] = getattr(instance_of_camera,
                                                 method_name)
