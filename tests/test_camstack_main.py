from __future__ import annotations

import pytest

import sys, time

from camstack import main
from pyMilk.interfacing.shm import SHM

from camstack.core import tmux


def test_camstack_main():
    orig_argv = sys.argv

    main.main(cam_name_arg='simucam')

    t_start_wait = time.time()
    s = None
    while time.time() - t_start_wait < 15.0:
        time.sleep(0.01)
        try:
            s = SHM('simuquest')
            break
        except:
            pass

    # Could assert tmux existence, etc.
    assert s is not None
    d = s.multi_recv_data(100)

    sys.argv = ['python', 'simucam', '-k']
    main.main()  # Should do a clean release with ctrl shell exit

    dat = s.get_data(True, timeout=1, return_none_on_timeout=True)
    assert dat is None

    tmux.find_or_create('simucam_ctrl').kill()
    tmux.find_or_create('simuquest_fgrab').kill()

    sys.argv = orig_argv
