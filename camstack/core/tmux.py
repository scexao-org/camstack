import libtmux as tmux

import os
import time
import subprocess

TMUX_SERVER = tmux.Server()  # Singleton


def find_or_create_(session_name: str):
    '''
        Return a handle to the active_pane in the "session_name" tmux session
        Create it if necessary.
        This relies on our extensive use of single-pane sessions.
    '''

    session = TMUX_SERVER.windows.get(session_name=session_name, default=None)
    if session is None:
        session = TMUX_SERVER.new_session(session_name)

    pane = session.attached_pane

    return pane


def find_or_create_deprecated(session_name: str):
    '''
        Mimic of find_or_create, but on a deprecated (tmux < 2.0) machine.
        Will return a DeprecatedPanePatch object
    '''
    cmd = "tmux new-session -d -s " + session_name
    subprocess.run(cmd.split(' '), stdout=subprocess.PIPE)
    return DeprecatedPanePatch(session_name)


if os.environ.get('WHICHCOMP', default=None) == '2':
    find_or_create = find_or_create_deprecated
else:
    find_or_create = find_or_create_


def find_or_create_remote(session_name: str, host: str):
    '''
        Mimic of find_or_create, but on a remote machine.
        Will return a RemotePanPatch object
    '''
    subprocess.run(['ssh', host, "tmux new-session -d -s " + session_name],
                   stdout=subprocess.PIPE)
    return RemotePanePatch(session_name, host)


def send_keys(pane, keys, enter=True):
    # This does NOT error if the tmux was destroyed !
    # Mind the different behavior with RemotePanePatch
    pane.send_keys(keys, enter=enter, suppress_history=False)


def kill_running_Cc(pane):
    pane.send_keys('C-c', enter=False, suppress_history=False)
    pane.send_keys('C-c', enter=False, suppress_history=False)


def kill_running_Cz(pane):
    pane.send_keys('C-z', enter=False, suppress_history=False)
    pane.send_keys('kill %')


def kill_running(pane):
    kill_running_Cc(pane)
    time.sleep(2.0)  # We need longer time for dcamusbtake to clear
    kill_running_Cz(pane)


def find_pane_running_pid(pane):
    # Identify the PIDs running in a pane.
    # Generally, we expect to find nothing, or only one front-end job.

    # This is the PID of the pane's shell
    p = pane.cmd('list-panes', '-F#{pane_pid}').stdout[0].strip()
    # For which we identify children
    if type(pane) is RemotePanePatch:
        res = subprocess.run(['ssh', pane.host, "pgrep", "-P", p],
                             stdout=subprocess.PIPE)
    else:
        res = subprocess.run(['pgrep', '-P', p], stdout=subprocess.PIPE)

    if res.returncode == 0:
        return int(res.stdout.decode(
                'utf8').strip())  # A fail here will probably mean many children
    else:
        return None


class DeprecatedPanePatch:

    def __init__(self, session_name: str):
        self.session_name = session_name

    def send_keys(self, keys: str, enter: bool = True,
                  suppress_history: bool = False):
        if suppress_history:
            keys = " " + keys
        cmdstring = ['tmux', 'send-keys', '-t', self.session_name, keys]
        if enter:
            cmdstring += ["Enter"]

        # Use check call to return a CalledProcessError
        subprocess.check_call(cmdstring, stdout=subprocess.PIPE)

    def cmd(self, command: str, args: str = ''):
        '''
            Carefully mind the single and double quotes
        '''
        cmdstring = ['tmux', command, '-t', self.session_name, args]
        return subprocess.run(cmdstring, stdout=subprocess.PIPE)


class RemotePanePatch:
    '''
        Provide a virtual handle to a tmux pane on a remote server
        It's only based on system tmux commands over ssh
    '''

    def __init__(self, session_name: str, host: str):
        self.session_name = session_name
        self.host = host

    def send_keys(self, keys: str, enter: bool = True,
                  suppress_history: bool = False):
        # Mind the quotes - we're gonna put keys between double quotes,
        # so we need to escape double quotes inside of keys
        # and we need to escape the backslash so that python knows it's a backslash
        if '"' in keys:
            keys = keys.replace('"', '\\"')
        if suppress_history:
            keys = " " + keys
        cmdstring = [
                'tmux', 'send-keys', '-t', self.session_name, '"' + keys + '"'
        ]
        if enter:
            cmdstring += ["Enter"]

        # Use check call to return a CalledProcessError
        subprocess.check_call(['ssh', self.host] + cmdstring,
                              stdout=subprocess.PIPE)

    def cmd(self, command: str, args: str = ''):
        '''
            Carefully mind the single and double quotes
        '''
        cmdstring = ['tmux', command, '-t', self.session_name, args]
        return subprocess.run(['ssh', self.host] + cmdstring,
                              stdout=subprocess.PIPE)
