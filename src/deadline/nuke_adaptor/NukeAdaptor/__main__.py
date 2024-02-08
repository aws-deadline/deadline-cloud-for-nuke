# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import logging
import sys
import typing
import pathlib

from openjd.adaptor_runtime import EntryPoint

from .adaptor import NukeAdaptor

__all__ = ["main"]
_logger = logging.getLogger(__name__)


def main(reentry_exe: typing.Optional[pathlib.Path] = None) -> int:
    """
    Entry point for the Nuke Adaptor
    """
    _logger.info("About to start the NukeAdaptor")

    package_name = vars(sys.modules[__name__])["__package__"]
    if not package_name:
        raise RuntimeError(f"Must be run as a module. Do not run {__file__} directly")

    try:
        EntryPoint(NukeAdaptor).start(reentry_exe=reentry_exe)
    except Exception as e:
        _logger.error(f"Entrypoint failed: {e}")
        return 1

    _logger.info("Done NukeAdaptor main")
    return 0


if __name__ == "__main__":
    sys.exit(main())
