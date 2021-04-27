#!/bin/env python
'''
    Cython compiled file to be used with setuid

    How to compile:
        sudo make all in camstack/camstack/core
        cp make_cset_and_rt in the PATH. setup.py should do it but doesn't seem to work.

    Usage:
        make_cset_and_rt <pid> <prio> [<cset>]

    Options:
        <pid>:      pid to move
        <prio>:     priority to give (SCHED FIFO will be used)
        <cset>:     cpuset


'''

import os, sys, subprocess

def make_cset_and_rt(pid: int, cset: str, prio: int):
    '''
        Move to a cset and give real-time priority

        To be efficient, must be called BEFORE any thread-spawning library
        Typically: numpy.
    '''

    # Find it (for print)
    print('Looking up process:')
    subprocess.run([f'ps',f'{pid}'], check=True)
    print(f'And elevating to prio {prio} (FIFO) in cpuset {cset}')

    print(f'UID, GID: {os.getuid()}, {os.getgid()}')

    ret = subprocess.run(['cset', 'proc', '--threads', '--force', '-m', str(pid), cset])
    if ret.returncode != 0:
        print(f'Not setting RT priority - cset {cset} does not exist')
        return

    os.system(f'chrt -f -p {prio} {pid}')


if __name__ == "__main__":

    import sys

    argc = len(sys.argv)
    if argc < 3 or argc > 4:
        raise ValueError('make_cset_and_rt <pid> <prio> [<cset>]')

    pid = int(sys.argv[1])
    prio = int(sys.argv[2])
    cset = 'system'
    if argc == 4:
        cset = sys.argv[3]

    make_cset_and_rt(pid, cset, prio)