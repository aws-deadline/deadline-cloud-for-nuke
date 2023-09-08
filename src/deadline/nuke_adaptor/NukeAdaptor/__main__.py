# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import logging as _logging
import sys as _sys

from openjobio.adaptor_runtime import EntryPoint as _EntryPoint

from .adaptor import NukeAdaptor

__all__ = ["main"]
_logger = _logging.getLogger(__name__)


def main() -> None:
    """
    Entry point for the Nuke Adaptor
    """
    _logger.info("About to start the NukeAdaptor")

    package_name = vars(_sys.modules[__name__])["__package__"]
    if not package_name:
        raise RuntimeError(f"Must be run as a module. Do not run {__file__} directly")

    try:
        _EntryPoint(NukeAdaptor).start()
    except Exception as e:
        _logger.error(f"Entrypoint failed: {e}")
        _sys.exit(1)

    _logger.info("Done NukeAdaptor main")


if __name__ == "__main__":
    main()
