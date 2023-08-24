# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""
Functionality for creating a global logger for the Nuke submitter.
"""
import logging
import logging.handlers
import os
import tempfile

# TODO: Output logging to the Script Editor Console as well.


class NukeLogger(logging.Logger):
    log_path = os.path.expanduser("~/.deadline/logs/submitters/nuke.log")

    def __init__(self, name):
        super().__init__(name)

        log_file = self.log_path

        if not os.path.exists(os.path.dirname(log_file)):
            # make sure the directories exist.
            try:
                os.makedirs(os.path.dirname(log_file))
            except (IOError, OSError):
                log_file = os.path.join(tempfile.gettempdir(), f"nuke.{os.getpid()}.log")

        if not os.access(os.path.dirname(log_file), os.W_OK | os.R_OK):
            # if we can't access the log file use a temp file.
            log_file = os.path.join(tempfile.gettempdir(), f"nuke.{os.getpid()}.log")

        disk_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10485760, backupCount=5
        )

        # we use a different format for the disk log, to get a time stamp.
        fmtf = logging.Formatter(
            "%(asctime)s %(levelname)8s {%(threadName)-10s}"
            ":  %(module)s %(funcName)s: %(message)s"
        )
        disk_handler.setFormatter(fmtf)
        self.addHandler(disk_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Retrieves the specified logger.
    """
    logging_class = logging.getLoggerClass()
    logging.setLoggerClass(NukeLogger)
    logger = logging.getLogger(name)
    logging.setLoggerClass(logging_class)

    return logger
