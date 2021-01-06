#!/bin/env python

'''
    Main camstack starter

    Will boot the server for your camera (in a tmux) and initialize a given mode
    TODO: cpusets and RTprios - setuid on EDTtake ?

    Usage:
        camstack.main <name> <unit> [-c <channel>] [-m <cam_mode>]
'''

from docopt import docopt


import libtmux as tmux

if __name__ == "__main__":
    # Process the args:
    args = docopt(__doc__)
    name = args['<name>']
    pdv_unit = args['<unit>']
    pdv_channel = args['<channel>']
    inital_cropmode = args['<cam_mode>']

    tmux_server_name = name + '_ctrl'
    tmux_run_name = name + '_run'

    # Build/grab the tmux sessions
    tms = tmux.Server()
    session_srv = tms.find_where({'session_name': tmux_server_name})
    session_run = tms.find_where({'session_name': tmux_run_name})

    if session_srv is None:
        session_srv = tms.new_session(tmux_server_name)
    pane_srv = session_srv.attached_pane

    if session_run is None:
        session_run = tms.new_session(tmux_run_name)
    pane_run = session_run.attached_pane

    # Clear existing stuff - hardcore way
    for pane in [pane_srv, pane_run]:
        pane.send_keys('C-c', enter=False, suppress_history=False)
        pane.send_keys('C-z', enter=False, suppress_history=False)
        pane.send_keys('kill %')

    # Start the server
    server_command = f'ipython -im camstack.camstack_server_main -- {name} {pdv_unit}'
    if pdv_channel is not None:
        server_command += f' -c {pdv_channel}'
    if inital_cropmode is not None:
        server_command += f' -m {inital_cropmode}'

    pane_srv.send_keys(server_command)
    




