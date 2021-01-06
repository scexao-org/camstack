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

    # Build the tmux session
    tms = tmux.Server()
    session_server = tms.find_where({'session_name': tmux_server_name})
    session_run = tms.find_where({'session_name': tmux_server_name})

    


