# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

import re
import os
from os.path import commonpath, dirname, join, normpath, samefile, isfile
from dataclasses import dataclass
from sys import platform
import nuke

from deadline.client.job_bundle.submission import AssetReferences
from deadline.client.exceptions import DeadlineOperationError
from deadline.nuke_util import ocio as nuke_ocio

FRAME_VIEW_EXPRESSION_REGEX = re.compile(r"(%(\d*)d)|(%[vV])", re.IGNORECASE)
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


def get_scene_asset_references() -> AssetReferences:
    """Traverses all nodes to determine both input and output asset references"""
    nuke.tprint("Walking node graph to auto-detect input/output asset references...")
    asset_references = AssetReferences()
    script_file = get_nuke_script_file()
    if not isfile(script_file):
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

                if iopath.is_file:
                    asset_references.input_filenames.add(iopath.path)
                else:
                    asset_references.input_directories.add(iopath.path)
        else:
            for iopath in get_output_paths_for_filenode(node):
                if iopath.is_file:
                    asset_references.output_directories.add(dirname(iopath.path))
                else:
                    asset_references.output_directories.add(iopath.path)

    if nuke_ocio.is_OCIO_enabled():
        # Determine and add the config file and associated search directories
        ocio_config_path = nuke_ocio.get_ocio_config_path()
        # Add the references
        if ocio_config_path is not None:
            if isfile(ocio_config_path):
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

        # gets the file path, still containing %04d, %v or TCL expressions.
        # note #### syntax for frames will be converted to %04d
        # note backslashes for windows paths are converted to forward slashes
        filepath = knob.value()
        # evaluate any tcl expressions in the path
        filepath = evaluate_tcl_subexpressions(filepath)

        expression_match = FRAME_VIEW_EXPRESSION_REGEX.search(filepath)
        path_is_file = True
        if expression_match:
            # in the case of an expression for frames / views, we will used the parent directory
            # of the filenode containing the first expression

            pos = expression_match.start()
            # walk back to the nearest /
            while pos >= 0 and filepath[pos] != "/":
                pos -= 1

            if pos == -1:
                filepath = "./"
            else:
                filepath = filepath[: pos + 1]

            path_is_file = False

        project_path = get_project_path()
        full_path = normpath(join(project_path, filepath))
        out.add(IOPath(path=full_path, is_file=path_is_file))

    return out


def evaluate_tcl_subexpressions(string: str) -> str:
    """Walk through a string, finding any tcl expressions (which are wrapped by []),
    and replace them with their evaluation"""

    # using list, then combining with join for efficiency
    evaluated_string = []
    bracket_nest_count = 0
    current_tcl_expression = []

    for c in string:
        if c == "[":
            # need to keep the [] for subexpressions
            if bracket_nest_count > 0:
                current_tcl_expression.append(c)

            bracket_nest_count += 1

        elif c == "]":
            bracket_nest_count -= 1
            if bracket_nest_count == 0:
                # end tcl expression
                evaluated_string.append(nuke.tcl("".join(current_tcl_expression)))
                current_tcl_expression = []  # reset for any subsequent expressions
            else:
                # need to keep the [] for subexpressions
                current_tcl_expression.append(c)

        elif bracket_nest_count > 0:
            # we are in an expression
            current_tcl_expression.append(c)
        else:
            evaluated_string.append(c)

    return "".join(evaluated_string)
