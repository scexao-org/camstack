from typing import Tuple, List, TypeVar, Optional as Op, Any, Union

import os
import time
import subprocess

from camstack.core import tmux


class CamstackStateException(Exception):
    pass


T = TypeVar('T')


def enforce_optional(anything: Op[T]) -> T:
    if anything is None:
        raise CamstackStateException('None shall not pass.')
    return anything


ModeIDType = Union[str, int]
ModeIDorHWType = Union[ModeIDType, Tuple[int, int]]
CsetPrioType = Tuple[str, Op[int]]


class CameraMode:

    def __init__(self, *, x0: int = None, x1: int = None, y0: int = None,
                 y1: int = None, fps: float = None, tint: float = None,
                 binx: int = 1, biny: int = 1, fgsize: Tuple[int, int] = None):

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

    def __str__(self):
        s = f'Camera Mode: {self.x0}-{self.x1}, {self.y0}-{self.y1} ({self.x1 - self.x0 + 1} x {self.y1 - self.y0 + 1})'
        if self.fps is not None:
            s += f' - {self.fps:.2f} Hz'
        if self.tint is not None:
            s += f' - {self.tint * 1e3:.1f} ms'
        s += f' - bin {self.binx} x {self.biny} - FGsize {self.fgsize}'

        return s


class DependentProcess:
    '''
        Dependent processes are stuff that the camera server should take care of killing before changing the size
        and restarting after changing the size.

        They're expected to live in a tmux (local or remote)
        This typically will include ocamdecode, and the TCP transfer.
    '''

    def __init__(self, tmux_name: str, cli_cmd: str, cli_args: List[str],
                 cset: str = 'system', rtprio: int = None,
                 kill_upon_create: bool = True):

        self.enabled = True  # Is this registered to run ? #TODO UNUSED

        self.tmux_name = tmux_name
        self.cli_cmd = cli_cmd
        self.cli_original_args = cli_args  # Can hold magic replace-me placeholders, e.g. #HEIGHT#
        self.cli_args = cli_args  # Then the placeholders get overwritten

        self.start_order = 0
        self.kill_order = 0

        self.cset = cset
        self.rtprio = rtprio

        self.kill_upon_init = kill_upon_create

    def assign_tmux_pane(self):
        self.tmux_pane = tmux.find_or_create(self.tmux_name)

    def initialize_tmux(self, kill_upon_create):
        self.assign_tmux_pane()
        if kill_upon_create:
            time.sleep(3.0)  # MUST NOT KILL the sourcing of bashrc/profile
            self.stop()

    def start_command_line(self):
        tmux.send_keys(self.tmux_pane, self.cli_cmd % self.cli_args)

    def start(self):
        self.start_command_line()
        time.sleep(1)
        self.make_children_rt()

    def make_children_rt(self):
        if self.rtprio is not None:
            # This works very partially.
            # Because some dependents start aux processes,
            # And because some dependents start by a sleep command...
            # D'oh.
            pids = []
            pid = self.get_pid()
            if pid is not None:
                pids = [pid]
            while len(pids) > 0:
                pid = pids.pop()
                #print('PID: ', pid)
                ret = subprocess.run([
                        'milk-makecsetandrt',
                        str(pid), self.cset,
                        str(self.rtprio)
                ], stdout=subprocess.DEVNULL)
                children = subprocess.run(['pgrep', '-P',
                                           str(pid)],
                                          stdout=subprocess.PIPE).stdout.decode(
                                                  'utf8').strip().split('\n')
                if children[0] != '':
                    pids += [int(c) for c in children]
                #print('PIDs: ', pids)

    def stop(self):
        tmux.kill_running_Cc(self.tmux_pane)
        time.sleep(2)
        tmux.kill_running_Cz(self.tmux_pane)
        time.sleep(1)

    def is_running(self):
        return self.get_pid() is not None

    def get_pid(self):
        return tmux.find_pane_running_pid(self.tmux_pane)


class RemoteDependentProcess(DependentProcess):

    def __init__(self, tmux_name, cli_cmd, cli_args, remote_host,
                 cset: str = None, rtprio: int = None,
                 kill_upon_create: bool = True):

        self.remote_host = remote_host

        DependentProcess.__init__(self, tmux_name, cli_cmd, cli_args, cset=cset,
                                  rtprio=rtprio,
                                  kill_upon_create=kill_upon_create)

    def assign_tmux_pane(self):
        self.tmux_pane = tmux.find_or_create_remote(self.tmux_name,
                                                    self.remote_host)

    def start(self):
        try:
            tmux.send_keys(self.tmux_pane, self.cli_cmd % self.cli_args)
        except subprocess.CalledProcessError as err:
            print(f"Remote {self.tmux_name} on {self.remote_host} tmux may be dead - attempting re-initialize"
                  )
            self.initialize_tmux(False)
            tmux.send_keys(self.tmux_pane, self.cli_cmd % self.cli_args)

        time.sleep(1)
        self.make_children_rt()


class DependentMultiManager:
    # The only point is to batch all the sleeping... that piles up quite a bit with lots of dependents.

    def __init__(self, dependents: List[DependentProcess]) -> None:
        self.dependent_list = dependents

    def initialize_tmux(self):
        for dependent in self.dependent_list:
            dependent.assign_tmux_pane()
        time.sleep(3.0)

        self.stop(watch_kill_create_flag=True)

    def start(self):
        self.dependent_list.sort(key=lambda x: x.start_order)

        for dependent in self.dependent_list:
            dependent.start_command_line()
        time.sleep(1.0)
        for dependent in self.dependent_list:
            dependent.make_children_rt()

    def stop(self, watch_kill_create_flag: bool = False):
        self.dependent_list.sort(key=lambda x: x.kill_order)
        for dependent in self.dependent_list:
            if (not watch_kill_create_flag) or dependent.kill_upon_init:
                tmux.kill_running_Cc(dependent.tmux_pane)
        time.sleep(2.0)
        for dependent in self.dependent_list:
            if (not watch_kill_create_flag) or dependent.kill_upon_init:
                tmux.kill_running_Cz(dependent.tmux_pane)
        time.sleep(.5)


def shellify_methods(instance_of_camera, top_level_globals):
    '''

    '''
    for method_name in instance_of_camera.INTERACTIVE_SHELL_METHODS:
        top_level_globals[method_name] = getattr(instance_of_camera,
                                                 method_name)


def enforce_whichcomp(comp: str):
    '''
        For scripts: enforce we're running on the right computer using the WHICHCOMP variable
    '''
    this_comp = os.environ.get('WHICHCOMP', '')
    if this_comp != comp:
        raise SystemError(
                f"WHICHCOMP variable {this_comp} doesn't match {comp}.\nYou need to be on the right computer to run this script."
        )
