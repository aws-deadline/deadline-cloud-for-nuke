# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

import os
import re
from collections.abc import Generator
from os.path import commonpath, dirname, join, normpath, samefile
from sys import platform
import nuke

from deadline.client.job_bundle.submission import AssetReferences
from deadline.client.exceptions import DeadlineOperationError
from deadline.nuke_util import ocio as nuke_ocio

FRAME_REGEX = re.compile(r"(#+)|%(\d*)d", re.IGNORECASE)
FILE_KNOB_CLASS = "File_Knob"
NUKE_WRITE_NODE_CLASSES: set[str] = {"Write", "DeepWrite", "WriteGeo"}
JOB_ID_REGEX = re.compile(r"^job-[0-9a-z]{32}$")


def get_nuke_script_file() -> str:
    """Gets the nuke script file (.nk)"""
    script_path = nuke.root().knob("name").value()
    if script_path:
        return normpath(script_path)
    return ""


def get_project_path() -> str:
    """This is the path Nuke uses for relative paths"""
    project_path = nuke.root().knob("project_directory").getEvaluatedValue()
    if not project_path:
        project_path = os.getcwd()
    return project_path


def get_scene_asset_references() -> AssetReferences:
    """Traverses all nodes to determine both input and output asset references"""
    nuke.tprint("Walking node graph to auto-detect input/output asset references...")
    asset_references = AssetReferences()
    script_file = get_nuke_script_file()
    if not os.path.isfile(script_file):
        raise DeadlineOperationError(
            "The Nuke Script is not saved to disk. Please save it before opening the submitter dialog."
        )
    asset_references.input_filenames.add(script_file)
    for node in nuke.allNodes(recurseGroups=True):
        # do not need assets for disabled nodes
        if node.knob("disable") and node.knob("disable").value():
            continue

        # write nodes can be turned into read nodes to avoid recomputation
        is_read_node = False
        read_knob = node.knob("reading")
        if read_knob:
            is_read_node = read_knob.value()

        if is_read_node or node.Class() not in NUKE_WRITE_NODE_CLASSES:
            for filename in get_node_filenames(node):
                # if the filename is in the install dir, ignore it.
                if node is nuke.root():
                    # Windows / Linux
                    install_path = dirname(nuke.EXE_PATH)
                    if platform.startswith("darwin"):
                        # EXE_PATH: /Applications/Nuke15.0v2/Nuke15.0v2.app/Contents/MacOS/Nuke15.0
                        # INSTALL_PATH: /Applications/Nuke15.0v2/Nuke15.0v2.app
                        install_path = dirname(dirname(dirname(nuke.EXE_PATH)))
                    try:
                        common_file_path = commonpath((filename, install_path))
                    except ValueError:
                        # Occurs if different drives, or mix of absolute + relative paths
                        pass
                    else:
                        if samefile(install_path, common_file_path):
                            continue
                if not os.path.isdir(filename):
                    asset_references.input_filenames.add(filename)
        else:
            for filename in get_node_filenames(node):
                asset_references.output_directories.add(dirname(filename))

    if nuke_ocio.is_OCIO_enabled():
        # Determine and add the config file and associated search directories
        ocio_config_path = nuke_ocio.get_ocio_config_path()
        # Add the references
        if ocio_config_path is not None:
            if os.path.isfile(ocio_config_path):
                asset_references.input_filenames.add(ocio_config_path)

                ocio_config_search_paths = nuke_ocio.get_config_absolute_search_paths(
                    ocio_config_path
                )
                for search_path in ocio_config_search_paths:
                    asset_references.input_directories.add(search_path)
            else:
                raise DeadlineOperationError(
                    "OCIO config file specified(%s) is not an existing file. Please check and update the config file before proceeding."
                    % ocio_config_path
                )

    return asset_references


def find_all_write_nodes() -> set:
    write_nodes = set()

    for node in nuke.allNodes():
        if node.Class() in NUKE_WRITE_NODE_CLASSES:
            # ignore write nodes if disabled
            if node.knob("disable").value():
                continue

            # ignore if WriteNode is being used as read node
            read_knob = node.knob("reading")
            if read_knob and read_knob.value():
                continue

            write_nodes.add(node)

    return write_nodes


def get_node_filenames(node) -> set[str]:
    """Searches through all of a node's file knobs for potential filenames.

    Handles '%04d' or '####' style padding
    """
    filenames: set[str] = set()
    for path in get_node_file_knob_paths(node):
        found_frame_pattern = FRAME_REGEX.search(path)
        if not found_frame_pattern:
            filenames.add(path)
            continue

        # frame token pattern exists in filename
        if found_frame_pattern.group(1):  # (#+)
            padding_length = len(found_frame_pattern.group(1))  # type: int
        else:  # %(\d*)d
            # If no integer is provided, use 1 for the padding
            padding_length = 1
            if found_frame_pattern.group(2):
                padding_length = int(found_frame_pattern.group(2))

        for frame in node.frameRange():
            evaluated_frame_string = str(frame).zfill(padding_length)
            evaluated_filename = FRAME_REGEX.sub(evaluated_frame_string, path)  # type: str
            filenames.add(evaluated_filename)

    return filenames


def get_node_file_knob_paths(node) -> Generator[str, None, None]:
    """Gets all file paths associated with a node"""
    project_path = get_project_path()
    for knob in node.allKnobs():
        if knob.Class() == FILE_KNOB_CLASS and knob.value():
            # If the knob value starts with a tcl expression, we evaluate it
            if knob.value().startswith("["):
                yield normpath(join(project_path, knob.getEvaluatedValue()))
            else:
                yield normpath(join(project_path, knob.value()))
