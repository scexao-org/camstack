import os, sys
import logging as logg
from logging import handlers as logghandlers


def init_camstack_logger(file_fullpath: str, file_debug: bool = False) -> None:
    stdouthandler = logg.StreamHandler(sys.stdout)
    stdouthandler.setLevel(logg.WARNING)

    logfilehandler = logghandlers.RotatingFileHandler(
            file_fullpath, maxBytes=1048576,
            backupCount=5)  # TODO rotating files, max length ???
    logfilehandler.setLevel((logg.INFO, logg.DEBUG)[file_debug])

    handlers = [stdouthandler, logfilehandler]

    logg.basicConfig(
            format=
            "[%(asctime)s] p%(process)s {%(pathname)s:%(lineno)d}\t%(levelname)s - %(message)s",
            handlers=handlers, level=logg.DEBUG)
