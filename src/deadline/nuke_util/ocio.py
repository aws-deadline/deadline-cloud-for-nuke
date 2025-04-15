# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

import os
from pathlib import PurePath
from typing import Optional

import nuke
import PyOpenColorIO as OCIO


def is_env_config_enabled() -> bool:
    """True if the OCIO environment variable is specified"""
    return "OCIO" in os.environ


def get_env_config_path() -> Optional[str]:
    """This is the path to the custom OCIO config used by the OCIO env var."""
    return os.environ.get("OCIO")


def is_stock_config_enabled() -> bool:
    """True if the script is using a default OCIO config"""
    return (
        nuke.root().knob("colorManagement").value() == "OCIO"
        and nuke.root().knob("OCIO_config").value() != "custom"
    )


def get_stock_config_path() -> str:
    """This is the path to the UI defined OCIO config file."""
    return os.path.abspath(nuke.root().knob("OCIOConfigPath").getEvaluatedValue())


def is_OCIO_enabled() -> bool:
    """Nuke is set to use OCIO."""
    return nuke.root().knob("colorManagement").value() == "OCIO"


def is_custom_config_enabled() -> bool:
    """True if the script is using a custom OCIO config"""
    return (
        nuke.root().knob("colorManagement").value() == "OCIO"
        and nuke.root().knob("OCIO_config").value() == "custom"
    )


def get_custom_config_path() -> str:
    """This is the path to the custom OCIO config used by the script"""
    return os.path.abspath(nuke.root().knob("customOCIOConfigPath").getEvaluatedValue())


def create_config_from_file(ocio_config_path: str) -> OCIO.Config:
    """Creates an OCIO config from the custom OCIO config path"""
    return OCIO.Config.CreateFromFile(ocio_config_path)


def config_has_absolute_search_paths(ocio_config: OCIO.Config) -> bool:
    """True if any paths in the OCIO config's search path are absolute"""
    return any(PurePath(path).is_absolute() for path in ocio_config.getSearchPaths())


def get_config_absolute_search_paths(ocio_config: str | OCIO.Config) -> list[str]:
    """Returns the directories containing the LUTs for the provided OCIO config"""
    if isinstance(ocio_config, str):
        ocio_config = OCIO.Config.CreateFromFile(ocio_config)

    # A config can have multiple search paths and they can be relative or absolute.
    # At least for all of the AMPAS OCIO configs this is always a single relative path to the "luts" directory
    search_paths = ocio_config.getSearchPaths()
    ocio_config_dir = ocio_config.getWorkingDir()

    return [os.path.join(ocio_config_dir, search_path) for search_path in search_paths]


def update_config_search_paths(ocio_config: OCIO.Config, search_paths: list[str]) -> None:
    """Replace the search path(s) in the provided OCIO config"""
    ocio_config.clearSearchPaths()
    for search_path in search_paths:
        ocio_config.addSearchPath(search_path)


def set_custom_config_path(ocio_config_path: str) -> None:
    """Set the knob on the root settings to update the OCIO config"""
    nuke.root().knob("customOCIOConfigPath").setValue(ocio_config_path)


def get_ocio_config_path() -> Optional[str]:
    """
    Get the path to the OCIO configurations. Supports:
        - OCIO environment variable
        - Custom config
        - Stock config
    Returns None if OCIO is not enabled
    """
    # if using a custom OCIO environment variable
    if is_env_config_enabled():
        return get_env_config_path()
    elif is_custom_config_enabled():
        return get_custom_config_path()
    elif is_stock_config_enabled():
        return get_stock_config_path()
    else:
        return None
