# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Dict, Optional
from os.path import commonpath, dirname, isfile, join, normpath, samefile
from sys import platform
import traceback

import nuke
from deadline.client.exceptions import DeadlineOperationError
from deadline.client.job_bundle.submission import AssetReferences

from deadline.nuke_util import ocio as nuke_ocio

# Nuke allows the use of printf style expressions in path names to be evaluated to the current frame number
# and view being rendered. For example %04d would be the current frame number zero padded to be at least 4 digits.
# %v or %V will be evaluated to the first character, or full name of the current view.
FRAME_VIEW_EXPRESSION_REGEX = re.compile(r"(%(\d*)d)|(%v)|(#+)", re.IGNORECASE)
FILE_KNOB_CLASS = "File_Knob"
NUKE_WRITE_NODE_CLASSES: set[str] = {"Write", "DeepWrite", "WriteGeo"}


@dataclass
class IOPath:
    path: str
    is_file: bool

    def __hash__(self):
        return self.path.__hash__()


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


@dataclass
class AssetReferencesParsingOutcome:
    asset_references: AssetReferences
    failed_to_parse_nodes: Dict[str, str]
    high_level_exception: Optional[str]

    def encountered_exception(self) -> bool:
        return self.high_level_exception is not None or len(self.failed_to_parse_nodes) > 0


def get_scene_asset_references() -> AssetReferencesParsingOutcome:
    """Traverses all nodes to determine both input and output asset references"""

    outcome = AssetReferencesParsingOutcome(
        asset_references=AssetReferences(), failed_to_parse_nodes={}, high_level_exception=None
    )

    script_file = get_nuke_script_file()
    if not isfile(script_file):
        raise DeadlineOperationError(
            "The Nuke Script is not saved to disk. Please save it before opening the submitter dialog."
        )

    try:
        nuke.tprint("Walking node graph to auto-detect input/output asset references...")
        outcome.asset_references.input_filenames.add(script_file)
        for node in nuke.allNodes(recurseGroups=True):
            try:
                # do not need assets for disabled nodes
                if node.knob("disable") and node.knob("disable").value():
                    continue

                # write nodes can be turned into read nodes to avoid recomputation
                is_read_node = False
                read_knob = node.knob("reading")
                if read_knob:
                    is_read_node = read_knob.value()

                if is_read_node or node.Class() not in NUKE_WRITE_NODE_CLASSES:
                    for iopath in get_input_paths_for_filenode(node):
                        # if the filename is in the install dir, ignore it.
                        if node is nuke.root():
                            # Windows / Linux
                            install_path = dirname(nuke.EXE_PATH)
                            if platform.startswith("darwin"):
                                # EXE_PATH: /Applications/Nuke15.0v2/Nuke15.0v2.app/Contents/MacOS/Nuke15.0
                                # INSTALL_PATH: /Applications/Nuke15.0v2/Nuke15.0v2.app
                                install_path = dirname(dirname(dirname(nuke.EXE_PATH)))
                            try:
                                common_file_path = commonpath((iopath.path, install_path))
                            except ValueError:
                                # Occurs if different drives, or mix of absolute + relative paths
                                pass
                            else:
                                if samefile(install_path, common_file_path):
                                    continue

                        # get_input_paths always returns filepaths, not directories.
                        outcome.asset_references.input_filenames.add(iopath.path)

                else:
                    for iopath in get_output_paths_for_filenode(node):
                        if iopath.is_file:
                            outcome.asset_references.output_directories.add(dirname(iopath.path))
                        else:
                            outcome.asset_references.output_directories.add(iopath.path)
            except Exception:
                outcome.failed_to_parse_nodes[node.name()] = traceback.format_exc()

        if nuke_ocio.is_OCIO_enabled():
            # Determine and add the config file and associated search directories
            ocio_config_path = nuke_ocio.get_ocio_config_path()
            # Add the references
            if ocio_config_path is not None:
                if isfile(ocio_config_path):
                    outcome.asset_references.input_filenames.add(ocio_config_path)

                    ocio_config_search_paths = nuke_ocio.get_config_absolute_search_paths(
                        ocio_config_path
                    )
                    for search_path in ocio_config_search_paths:
                        outcome.asset_references.input_directories.add(search_path)
                else:
                    raise DeadlineOperationError(
                        "OCIO config file specified(%s) is not an existing file. Please check and update the config file before proceeding."
                        % ocio_config_path
                    )
    except Exception:
        outcome.high_level_exception = traceback.format_exc()

    return outcome


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


def get_input_paths_for_filenode(node) -> set[IOPath]:
    """Get all the file we will use as input for this node"""

    out = set()
    for knob in node.allKnobs():
        if knob.Class() != FILE_KNOB_CLASS or not knob.value():
            continue

        context = nuke.OutputContext()
        views = nuke.views()
        project_path = get_project_path()

        for frame in node.frameRange():
            for view in views:
                context.setFrame(frame)
                context.setView(context.viewFromName(view))
                out.add(
                    IOPath(
                        path=normpath(join(project_path, knob.getEvaluatedValue(context))),
                        is_file=True,
                    )
                )

    return out


def get_output_paths_for_filenode(node) -> set[IOPath]:
    """Get the directores or files we will pass to job attachments to capture all files consumed as input / produced as output for this node"""

    out = set()
    for knob in node.allKnobs():
        if knob.Class() != FILE_KNOB_CLASS or not knob.value():
            continue

        # evaluate any tcl / python expressions in the path, while leaving view / frame number expressions intact
        filepath = nuke.filename(node)

        expression_match = FRAME_VIEW_EXPRESSION_REGEX.search(filepath)
        path_is_file = True
        if expression_match:
            # in the case of an expression for frames / views, we will used the parent directory
            # of the filenode containing the first expression
            nuke.tprint(
                f"found printf style expression {expression_match.group(0)} starting at index {expression_match.start()} in path {filepath}"
            )

            pos = expression_match.start()
            # walk back to the nearest /
            while pos >= 0 and filepath[pos] != "/":
                pos -= 1

            if pos == -1:
                nuke.tprint(
                    "Did not find a written directory above the filenode where the expression appears. Using ./ as the output path."
                )
                filepath = "./"
            else:
                filepath = filepath[: pos + 1]

            path_is_file = False

        project_path = get_project_path()
        full_path = normpath(join(project_path, filepath))
        out.add(IOPath(path=full_path, is_file=path_is_file))

    return out
