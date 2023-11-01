# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import random
from typing import Any, Dict, List
from unittest.mock import MagicMock, call, patch

import nuke
import pytest

import deadline.nuke_adaptor.NukeClient.nuke_handler as handler_mod
from deadline.nuke_adaptor.NukeClient.nuke_handler import NukeHandler

from test.unit.mock_stubs import MockKnob, MockNode


@pytest.fixture()
def nukehandler():
    return NukeHandler()


@pytest.fixture()
def proxy_knob() -> MockKnob:
    return MockKnob(True)


@pytest.fixture()
def views() -> List[str]:
    return ["left", "right", "main"]


@pytest.fixture()
def views_knob(views: List[str]) -> MockKnob:
    return MockKnob(" ".join(views))  # Nuke stores as space separated list


@pytest.fixture()
def root_node(proxy_knob: MockKnob, views_knob: MockKnob):
    knobs = {"proxy": proxy_knob, "views": views_knob}
    return MockNode(name="root", knobs=knobs, class_name="Root")


class SortedSet(set):
    """
    Nuke Handler makes use of sets which don't guarantee order, this is used
    so that string comparisons on strings containing an iterated set always
    have the same order.
    """

    def __iter__(self):
        for i in sorted(super().__iter__()):
            yield i


class SortedList(list):
    """
    Nuke Handler makes use of sets which don't guarantee order, this is used
    so that string comparisons on strings containing an iterated set always
    have the same order.
    """

    def __init__(self, seq=()):
        if isinstance(seq, set):
            seq = sorted(seq)
        super().__init__(seq)

    def __str__(self):
        return "[" + ", ".join(f"'{item}'" for item in self) + "]"

    def __repr__(self) -> str:
        return self.__str__()


@pytest.fixture()
def write_nodes(views) -> List[MockNode]:
    NUM_NODES = 5
    render_orders = [MockKnob(i) for i in range(NUM_NODES)]
    random.shuffle(render_orders)
    views_knobs = [
        MockKnob(" ".join(random.sample(views, k=random.randint(1, len(views)))))
        for _ in range(NUM_NODES)
    ]
    knobs = [
        {"views": views_knobs[i], "render_order": render_orders[i], "disable": MockKnob(False)}
        for i in range(NUM_NODES)
    ]
    write_nodes = [
        MockNode(name=f"Write{i}", knobs=knobs[i], class_name="Write") for i in range(NUM_NODES)
    ]
    return write_nodes


@pytest.fixture(autouse=True)
def setup_nuke(root_node: MockNode, views: List[str], write_nodes: List[MockNode]) -> None:
    nuke.root.return_value = root_node
    nuke.views.return_value = views
    nuke.allNodes.return_value = write_nodes


def _generate_progress_messages(nukehandler, write_nodes):
    original_write_nodes = nukehandler.write_nodes
    write_nodes.sort(key=lambda node: node.knobs()["render_order"].value())
    nukehandler.write_nodes = write_nodes
    output_counts = nukehandler._get_all_nodes_total_outputs()

    running_total = 0
    total_outputs = sum(output_counts)
    progress_messages = []
    for output in output_counts:
        progress_messages.append(
            f"NukeClient: Creating outputs {running_total}-{running_total + output} of "
            f"{total_outputs} total outputs."
        )
        running_total += output

    nukehandler.write_nodes = original_write_nodes
    return progress_messages


class TestNukeHandler:
    def test_get_all_nodes_total_outputs_no_views(
        self, nukehandler: NukeHandler, write_nodes: List[MockNode]
    ) -> None:
        # GIVEN
        nukehandler.write_nodes = write_nodes
        expected = [len(n.knobs()["views"].value().split(" ")) for n in write_nodes]

        # WHEN
        actual = nukehandler._get_all_nodes_total_outputs()

        # THEN
        assert expected == actual

    def test_get_all_nodes_total_outputs_with_views(
        self, nukehandler: NukeHandler, write_nodes: List[MockNode], views: List[str]
    ) -> None:
        # GIVEN
        nukehandler.write_nodes = write_nodes
        nukehandler.render_kwargs["views"] = views

        expected = [len(views)] * len(write_nodes)

        # WHEN
        actual = nukehandler._get_all_nodes_total_outputs()

        # THEN
        assert expected == actual

    @pytest.mark.parametrize("set_nodes", [True, False])
    @pytest.mark.parametrize("set_views", [True, False])
    @pytest.mark.parametrize("continueOnError", [True, False])
    @pytest.mark.parametrize("args", [{"frameRange": 99}])
    @patch.object(nuke, "execute")
    def test_start_render_single_frame(
        self,
        nuke_execute: MagicMock,
        nukehandler: NukeHandler,
        set_nodes: bool,
        write_nodes: List[MockNode],
        args: Dict,
        continueOnError: bool,
        set_views: bool,
        views: List[str],
        capsys,
    ):
        """Tests that starting a render calls the correct nuke functions"""
        # GIVEN
        render_kwargs: Dict[str, Any] = {"continueOnError": continueOnError}
        if set_views:
            render_kwargs["views"] = views

        if set_nodes:
            nukehandler.write_nodes = write_nodes

        nukehandler.render_kwargs = render_kwargs

        expected_progress_messages = _generate_progress_messages(nukehandler, write_nodes)
        frame = args["frameRange"]
        execute_calls = [call(node, frame, frame, 1, **render_kwargs) for node in write_nodes]

        # WHEN
        nukehandler.start_render(args)

        # THEN
        stdout = capsys.readouterr().out
        assert nukehandler.write_nodes == write_nodes
        assert (
            (
                "NukeClient: No write nodes were specified, running all write nodes: "
                f"{[node.name() for node in write_nodes]}"
            )
            in stdout
        ) != set_nodes
        for message in expected_progress_messages:
            assert message in stdout
        nuke_execute.assert_has_calls(execute_calls)

    @pytest.mark.parametrize("set_nodes", [True, False])
    @pytest.mark.parametrize("set_views", [True, False])
    @pytest.mark.parametrize("continueOnError", [True, False])
    @pytest.mark.parametrize("args", [{"frameRange": "5-10"}])
    @patch.object(nuke, "execute")
    def test_start_render_frame_range(
        self,
        nuke_execute: MagicMock,
        nukehandler: NukeHandler,
        set_nodes: bool,
        write_nodes: List[MockNode],
        args: Dict,
        continueOnError: bool,
        set_views: bool,
        views: List[str],
        capsys,
    ):
        """Tests that starting a render calls the correct nuke functions"""
        # GIVEN
        render_kwargs: Dict[str, Any] = {"continueOnError": continueOnError}
        if set_views:
            render_kwargs["views"] = views

        if set_nodes:
            nukehandler.write_nodes = write_nodes

        nukehandler.render_kwargs = render_kwargs

        expected_progress_messages = _generate_progress_messages(nukehandler, write_nodes)
        execute_calls = [call(node, 5, 10, 1, **render_kwargs) for node in write_nodes]

        # WHEN
        nukehandler.start_render(args)

        # THEN
        stdout = capsys.readouterr().out
        assert nukehandler.write_nodes == write_nodes
        assert (
            (
                "NukeClient: No write nodes were specified, running all write nodes: "
                f"{[node.name() for node in write_nodes]}"
            )
            in stdout
        ) != set_nodes
        for message in expected_progress_messages:
            assert message in stdout
        nuke_execute.assert_has_calls(execute_calls)

    @pytest.mark.parametrize("continueOnError", [True, False])
    @pytest.mark.parametrize("args", [{"frameRange": 99}])
    @patch.object(nuke, "execute")
    def test_start_render_exception(
        self,
        nuke_execute: MagicMock,
        nukehandler: NukeHandler,
        write_nodes: List[MockNode],
        args: Dict,
        continueOnError: bool,
        views: List[str],
        capsys,
    ):
        """
        Tests that starting a render that results in an exception behaves appropriately depending on
        the value of continueOnError
        """
        # GIVEN
        render_kwargs: Dict[str, Any] = {"continueOnError": continueOnError}
        render_kwargs["views"] = views
        nuke_execute.side_effect = RuntimeError("Could not run node because something bad happened")
        nukehandler.write_nodes = write_nodes

        nukehandler.render_kwargs = render_kwargs

        frame = args["frameRange"]
        execute_calls = []
        expected_err_messages = []
        for node in sorted(write_nodes, key=lambda node: node.knobs()["render_order"].value()):
            execute_calls.append(call(node, frame, frame, 1, **render_kwargs))
            expected_err_messages.append(
                "NukeClient: Encountered the following Exception while running node "
                f"'{node.name()}': '{str(nuke_execute.side_effect)}'"
            )
            if not continueOnError:
                break

        # WHEN
        if continueOnError:
            nukehandler.start_render(args)
        else:
            with pytest.raises(RuntimeError) as exc_info:
                nukehandler.start_render(args)

        # THEN
        captured = capsys.readouterr()
        print(captured.out)
        print(captured.err)
        stderr = captured.err

        for message in expected_err_messages:
            assert message in stderr

        if continueOnError:
            nuke_execute.assert_has_calls(execute_calls)
        else:
            assert exc_info.value is nuke_execute.side_effect
            nuke_execute.assert_called_once_with(*execute_calls[0].args, **execute_calls[0].kwargs)

    @pytest.mark.parametrize("args", [{}])
    @patch.object(nuke, "execute")
    def test_start_render_no_frame(
        self, nuke_execute: MagicMock, nukehandler: NukeHandler, args: Dict
    ):
        # WHEN
        with pytest.raises(Exception) as exc_info:
            nukehandler.start_render(args)

        # THEN
        assert str(exc_info.value) == "NukeClient: start_render called without a frameRange."
        nuke_execute.assert_not_called()

    def test_set_write_nodes(self, write_nodes: List[MockNode], nukehandler: NukeHandler):
        # GIVEN
        data = {"write_nodes": [node.name() for node in write_nodes]}

        # WHEN
        nukehandler.set_write_nodes(data)

        # THEN
        assert nukehandler.write_nodes == write_nodes

    def test_set_write_nodes_all_write_nodes(
        self, write_nodes: List[MockNode], nukehandler: NukeHandler
    ):
        # GIVEN
        all_write_nodes = ["All Write Nodes"]
        data = {"write_nodes": all_write_nodes}

        # WHEN
        nukehandler.set_write_nodes(data)

        # THEN
        assert nukehandler.write_nodes == write_nodes

    missing_nodes_params = [
        (
            SortedList(["these", "do", "not", "exist"]),
            RuntimeError(
                "The following nodes are missing from the script: ['do', 'exist', 'not', 'these']"
            ),
        ),
        (SortedList([]), RuntimeError("No write nodes were specified.")),
        (
            SortedList(["Write1", 0, 1, True, {}]),
            TypeError("Expected type list[str] for write nodes. Got list[bool, dict, int, str]."),
        ),
        ({"node": "Write1"}, TypeError("Expected type list[str] for write nodes. Got dict.")),
    ]

    @pytest.mark.parametrize("node_list, expected_err", missing_nodes_params)
    @patch.object(handler_mod, "list", new=SortedList)  # to guarantee order for string comparison
    @patch.object(handler_mod, "set", new=SortedSet)  # to guarantee order for string comparison
    def test_set_write_nodes_error(
        self, nukehandler: NukeHandler, node_list: Any, expected_err: str
    ):
        # GIVEN
        data = {"write_nodes": node_list}

        # WHEN
        with pytest.raises(Exception) as exc_info:
            nukehandler.set_write_nodes(data)

        # THEN
        assert type(exc_info.value) == type(expected_err)
        assert str(exc_info.value) == str(expected_err)

    def test_set_write_nodes_missing_nodes_wrong_type(self, nukehandler: NukeHandler):
        # GIVEN
        missing_nodes = ["these", "do", "not", "exist"]
        data = {"write_nodes": missing_nodes}

        # WHEN
        with pytest.raises(RuntimeError) as exc_info:
            nukehandler.set_write_nodes(data)

        # THEN
        assert (
            str(exc_info.value)
            == f"The following nodes are missing from the script: {sorted(set(missing_nodes))}"
        )

    @pytest.mark.parametrize(
        "data", [{"continue_on_error": True}, {"continue_on_error": False}, {}]
    )
    def test_set_continue_on_error(self, data: Dict, nukehandler: NukeHandler):
        # WHEN
        nukehandler.set_continue_on_error(data)

        # THEN
        assert nukehandler.render_kwargs["continueOnError"] == data.get("continue_on_error", True)

    @pytest.mark.parametrize("data", [{"proxy": True}, {"proxy": False}, {}])
    @patch.object(MockKnob, "setValue")
    def test_set_proxy(self, mock_set_value: MagicMock, data: Dict, nukehandler: NukeHandler):
        # WHEN
        nukehandler.set_proxy(data)

        # THEN
        nuke.root().knobs()["proxy"].setValue.assert_called_once_with(data.get("proxy", False))

    def test_set_views(self, views: List[str], nukehandler: NukeHandler):
        # GIVEN
        data = {"views": views}

        # WHEN
        nukehandler.set_views(data)

        # THEN
        assert nukehandler.render_kwargs["views"] == views

    missing_nodes_params = [
        (
            SortedList(["these", "do", "not", "exist"]),
            RuntimeError(
                "The following views are missing from the script: ['do', 'exist', 'not', 'these']"
            ),
        ),
        (SortedList([]), RuntimeError("No views were specified.")),
        (
            SortedList(["Write1", 0, 1, True, {}]),
            TypeError("Expected type list[str] for views. Got list[bool, dict, int, str]."),
        ),
        ({"view": "View1"}, TypeError("Expected type list[str] for views. Got dict.")),
    ]

    @pytest.mark.parametrize("node_list, expected_err", missing_nodes_params)
    @patch.object(handler_mod, "list", new=SortedList)  # to guarantee order for string comparison
    @patch.object(handler_mod, "set", new=SortedSet)  # to guarantee order for string comparison
    def test_set_views_error(self, nukehandler: NukeHandler, node_list: Any, expected_err: str):
        # GIVEN
        data = {"views": node_list}

        # WHEN
        with pytest.raises(Exception) as exc_info:
            nukehandler.set_views(data)

        # THEN
        assert type(exc_info.value) == type(expected_err)
        assert str(exc_info.value) == str(expected_err)

    @pytest.mark.parametrize("data", [{"script_file": "a/script/path.nk"}])
    @patch("os.path.isfile", return_value=True)
    @patch.object(nuke, "scriptOpen")
    def test_set_script_file(
        self,
        mock_script_open: MagicMock,
        mock_is_file: MagicMock,
        nukehandler: NukeHandler,
        data: Dict,
    ):
        # WHEN
        nukehandler.set_script_file(data)

        # THEN
        mock_is_file.assert_called_once_with(data["script_file"])
        mock_script_open.assert_called_once_with(data["script_file"])

    @pytest.mark.parametrize("data", [{"script_file": "a/script/path.nk"}])
    @patch("os.path.isfile", return_value=False)
    @patch.object(nuke, "scriptOpen")
    def test_set_script_file_is_not_file(
        self,
        mock_script_open: MagicMock,
        mock_is_file: MagicMock,
        nukehandler: NukeHandler,
        data: Dict,
    ):
        # GIVEN

        # WHEN
        with pytest.raises(FileNotFoundError) as exc_info:
            nukehandler.set_script_file(data)

        # THEN
        assert str(exc_info.value) == f"The script file '{data['script_file']}' does not exist"
        mock_script_open.assert_not_called()
