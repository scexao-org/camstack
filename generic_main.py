#!/bin/env python

'''
    Main camstack starter

    Will boot the server for your camera (in a tmux) and initialize a given mode
    TODO: cpusets and RTprios - setuid on EDTtake ?

    Usage:
        camstack.main [--server] <name> <unit> [init] [--channel=XX] [--cpuset=XX] [--rtprio=XX]

    Options:
        plop.
'''

import docopt


import the_tmux_utils

def main(args):
    if not args['--server']:
        # This is the main start - we build the server tmux, cd in the appropriate dir, and execute the same line, with ipython, in the tmux without the --server.
        pass
    else: # We are in the server tmux, so let's run the main
        # Process args (in particular, which cam, FG, channel)
        pass

    return locals()

if __name__ == "__main__":
    args = docopt.docopt(__doc__)
    locs = main(args)
    locals.update(locs)
