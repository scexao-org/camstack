import os
import logging as logg


def init_camstack_logger(file_fullpath: str, file_debug: bool = False) -> None:
    stdouthandler = logg.StreamHandler(os.sys.stdout)
    stdouthandler.setLevel(logg.WARNING)
    
    logfilehandler = logg.RotatingFileHandler(file_fullpath, maxBytes=1048576, backupCount=5) # TODO rotating files, max length ???
    logfilehandler.setLevel((logg.INFO, logg.DEBUG)[file_debug])

    handlers = [stdouthandler, logfilehandler]

    logg.basicConfig(
        format="[%(asctime)s] p%(process)s {%(pathname)s:%(lineno)d}\n\t%(levelname)s - %(message)s",
        handlers=handlers,
        level=logg.DEBUG)