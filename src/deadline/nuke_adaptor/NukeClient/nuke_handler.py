# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

import re
import os
import sys
from typing import TYPE_CHECKING, Any, Callable, Dict, List

try:
    import nuke
except ImportError:  # pragma: no cover
    raise OSError("Could not find the Nuke module. Are you running this inside of Nuke?")

if TYPE_CHECKING:  # pragma: no cover
    from nuke import Node


NUKE_WRITE_NODE_CLASSES = {"Write", "WriteGeo", "DeepWrite"}


class NukeHandler:
    action_dict: Dict[str, Callable[[Dict[str, Any]], None]] = {}
    render_kwargs: Dict[str, Any]
    write_nodes: List[Node]

    @property
    def continue_on_error(self) -> bool:
        return self.render_kwargs["continueOnError"]

    def __init__(self) -> None:
        """
        Constructor for the nuke handler. Initializes action_dict and render variables
        """
        self.action_dict = {
            "continue_on_error": self.set_continue_on_error,
            "proxy": self.set_proxy,
            "views": self.set_views,
            "script_file": self.set_script_file,
            "write_nodes": self.set_write_nodes,
            "start_render": self.start_render,
        }
        self.render_kwargs = {"continueOnError": True}
        self.write_nodes = []

    def start_render(self, data: dict) -> None:
        """
        Runs all write nodes for a given frameRange in Nuke, order that the write nodes are run is
        determined by the render order.

        Args:
            data (dict): The data given from the Adaptor. Keys expected: ['frameRange']

        Raises:
            RuntimeError: If start render is called without a frame number.
        """
        frame_range = data.get("frameRange", "")
        if frame_range == "":
            raise Exception("NukeClient: start_render called without a frameRange.")

        # FrameRange should be a string of the format "<startframe>-<endframe>" or "<frame>"
        match = re.match(r"(\d+)-(\d+)", frame_range)
        if match:
            start_frame = int(match.group(1))
            end_frame = int(match.group(2))

        else:
            match = re.match(r"(\d+)", frame_range)
            if not match:
                raise Exception(
                    f"Invalid frame range {frame_range}. The string frame range must follow the format '<startFrame>-<endFrame>' or '<frame>'"
                )

            start_frame = int(frame_range)
            end_frame = int(frame_range)

        if not self.write_nodes:
            self.write_nodes = NukeHandler._get_write_nodes()
            print(
                "NukeClient: No write nodes were specified, running all write nodes: "
                f"{[node.name() for node in self.write_nodes]}",
                flush=True,
            )

        # enforce render order
        self.write_nodes.sort(key=lambda node: node.knobs()["render_order"].value())

        # set up progress handling
        output_counts = self._get_all_nodes_total_outputs()
        running_total = 0
        total_outputs = sum(output_counts)

        # Run each write node
        for node, output in zip(self.write_nodes, output_counts):
            print(
                f"NukeClient: Creating outputs {running_total}-{running_total + output} of "
                f"{total_outputs} total outputs.",
                flush=True,
            )
            try:
                nuke.execute(node, start_frame, end_frame, 1, **self.render_kwargs)
            except Exception as e:
                print(
                    "NukeClient: Encountered the following Exception while running node "
                    f"'{node.name()}': '{e}'",
                    file=sys.stderr,
                    flush=True,
                )
                if not self.continue_on_error:
                    raise e

            running_total += output

        if end_frame > start_frame:
            print(f"NukeClient: Finished Rendering Frames {start_frame}-{end_frame}", flush=True)
        else:
            print(f"NukeClient: Finished Rendering Frame {start_frame}", flush=True)

    def _get_all_nodes_total_outputs(self) -> List[int]:
        """
        Creates a list of the number of outputs created by each node. This is determined by
        the number of views each node will create an output for.

        Returns:
            _List[int]: A list containg the number of outputs each node will create
        """
        if "views" in self.render_kwargs:
            num_views = len(self.render_kwargs["views"])
            return [num_views] * len(self.write_nodes)
        else:
            # If we aren't setting views to render with, then calculate based each node's views.
            # If there are space names in views there can be errors at render time, and the returned
            # value may be higher than the actual number of expected outputs.
            return [len(n.knobs()["views"].value().split(" ")) for n in self.write_nodes]

    def set_write_nodes(self, data: dict) -> None:
        """
        Sets the write nodes that will be run at render time.

        Args:
            data (dict): The data given from the Adaptor. Keys expected: ['write_nodes']

        Raises:
            RuntimeError: If node(s) are missing from the script.
        """
        nodes = data.get("write_nodes", [])
        NukeHandler._validate_non_empty_list_of_str(nodes, "write nodes")
        script_write_nodes = {node.name(): node for node in NukeHandler._get_write_nodes()}

        # The "All Write Nodes" value means to get all of them.
        if nodes == ["All Write Nodes"]:
            nodes = list(script_write_nodes.keys())

        # Validate nodes exist in the nuke script
        missing_nodes = set(nodes) - set(script_write_nodes.keys())
        if missing_nodes:
            raise RuntimeError(
                f"The following nodes are missing from the script: {sorted(missing_nodes)}"
            )
        self.write_nodes = [script_write_nodes[node_name] for node_name in sorted(nodes)]

    def set_continue_on_error(self, data: dict) -> None:
        """
        Sets the continueOnError flag to be used at render time.

        Args:
            data (dict): The data given from the Adaptor. Keys expected: ['continue_on_error']
        """
        self.render_kwargs["continueOnError"] = bool(data.get("continue_on_error", True))

    def set_proxy(self, data: dict) -> None:
        """
        Sets the flag to determine if nuke will be run in proxy mode or not.

        Args:
            data (dict): The data given from the Adaptor. Keys expected: ['proxy']
        """
        nuke.root().knobs()["proxy"].setValue(bool(data.get("proxy", False)))

    def set_views(self, data: dict) -> None:
        """
        Sets the views that will be used for each write node. All of the views provided will be
        used for every write node.

        Args:
            data (dict): The data given from the Adaptor. Keys expected: ['views']

        Raises:
            RuntimeError: If view(s) are missing from the script.
        """
        views = data.get("views", [])
        NukeHandler._validate_non_empty_list_of_str(views, "views")

        # The "All Views" value means to get all of them, and we do that per write node,
        # therefore we don't set self.render_kwargs["views"] in this case.
        if views == ["All Views"]:
            return

        # Validate views exist in the nuke script
        script_views = nuke.views()
        missing_views = set(views) - set(script_views)
        if missing_views:
            raise RuntimeError(
                f"The following views are missing from the script: {list(missing_views)}"
            )

        self.render_kwargs["views"] = views

    def set_script_file(self, data: dict) -> None:
        """
        Opens the script file in Nuke.

        Args:
            data (dict): The data given from the Adaptor. Keys expected: ['script_file']

        Raises:
            FileNotFoundError: If path to the script file does not yield a file
        """
        # The script path has already been path mapped because it is provided by a PATH parameter
        script_path = data.get("script_file", "")
        if not os.path.isfile(script_path):
            raise FileNotFoundError(f"The script file '{script_path}' does not exist")
        nuke.scriptOpen(script_path)

    @staticmethod
    def _get_write_nodes() -> List[Node]:
        write_nodes = []

        for node in nuke.allNodes():
            if node.Class() in NUKE_WRITE_NODE_CLASSES:
                # ignore write nodes if disabled
                if node.knob("disable").value():
                    continue

                # ignore if WriteNode is being used as read node
                read_knob = node.knob("reading")
                if read_knob and read_knob.value():
                    continue

                write_nodes.append(node)

        return write_nodes

    @staticmethod
    def _validate_non_empty_list_of_str(value: Any, name: str) -> None:
        """
        Runs validation on a value to ensure that it is of type List[str]

        Args:
            value (_Any): The value to validate
            name (str): The name of the value for error reporting. E.g. 'write nodes', 'views'

        Raises:
            RuntimeError: If the list is empty.
            TypeError: If the type of the value is not List[str]
        """
        if not isinstance(value, list):
            raise TypeError(f"Expected type list[str] for {name}. Got {type(value).__name__}.")
        elif not all(isinstance(node, str) for node in value):
            types = set(type(node).__name__ for node in value)
            raise TypeError(f"Expected type list[str] for {name}. Got list[{', '.join(types)}].")
        if not value:
            raise RuntimeError(f"No {name} were specified.")
