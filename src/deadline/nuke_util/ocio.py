# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

import os
from pathlib import PurePath

import nuke
import PyOpenColorIO as OCIO


def is_custom_config_enabled() -> bool:
    """True if the script is using a custom OCIO config"""
    return (
        nuke.root().knob("colorManagement").value() == "OCIO"
        and nuke.root().knob("OCIO_config").value() == "custom"
    )


def get_custom_config_path() -> str:
    """This is the path to the custom OCIO config used by the script"""
    return nuke.root().knob("customOCIOConfigPath").getEvaluatedValue()


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
