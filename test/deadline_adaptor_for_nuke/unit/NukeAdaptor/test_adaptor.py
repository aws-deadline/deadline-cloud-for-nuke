# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

import os
from unittest.mock import Mock, PropertyMock, call, patch

import pytest
import jsonschema  # type: ignore

import deadline.nuke_adaptor.NukeAdaptor.adaptor as adaptor_module
from deadline.nuke_adaptor.NukeAdaptor import NukeAdaptor
from deadline.nuke_adaptor.NukeAdaptor.adaptor import (
    _FIRST_NUKE_ACTIONS,
    _NUKE_INIT_KEYS,
    NukeNotRunningError,
)


@pytest.fixture()
def init_data() -> dict:
    """
    Pytest Fixture to return an init_data dictionary that passes validation

    Returns:
        dict: An init_data dictionary
    """
    return {
        "continue_on_error": True,
        "proxy": True,
        "write_nodes": ["Write1", "Write2", "Write3"],
        "views": ["left", "right"],
        "script_file": "/path/to/some/nukescript.nk",
    }


@pytest.fixture()
def run_data() -> dict:
    """
    Pytest Fixture to return a run_data dictionary that passes validation

    Returns:
        dict: A run_data dictionary
    """
    return {"frame": 42}


class TestNukeAdaptor_on_start:
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.ActionsQueue.__len__", return_value=0)
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.LoggingSubprocess")
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.AdaptorServer")
    def test_no_error(
        self,
        mock_server: Mock,
        mock_logging_subprocess: Mock,
        mock_actions_queue: Mock,
        init_data: dict,
    ) -> None:
        """Tests that on_start completes without error"""
        adaptor = NukeAdaptor(init_data)
        mock_server.return_value.socket_path = "/tmp/9999"
        adaptor.on_start()

    @patch("time.sleep")
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.ActionsQueue.__len__", return_value=0)
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.LoggingSubprocess")
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.AdaptorServer")
    def test_waits_for_server_socket(
        self,
        mock_server: Mock,
        mock_logging_subprocess: Mock,
        mock_actions_queue: Mock,
        mock_sleep: Mock,
        init_data: dict,
    ) -> None:
        """Tests that the adaptor waits until the server socket is available"""
        # GIVEN
        adaptor = NukeAdaptor(init_data)
        socket_mock = PropertyMock(
            side_effect=[None, None, None, "/tmp/9999", "/tmp/9999", "/tmp/9999"]
        )
        type(mock_server.return_value).socket_path = socket_mock

        # WHEN
        adaptor.on_start()

        # THEN
        assert mock_sleep.call_count == 3

    @patch("threading.Thread")
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.AdaptorServer")
    def test_server_init_fail(self, mock_server: Mock, mock_thread: Mock, init_data: dict) -> None:
        """Tests that an error is raised if no socket becomes available"""
        # GIVEN
        adaptor = NukeAdaptor(init_data)

        with patch.object(adaptor, "_SERVER_START_TIMEOUT_SECONDS", 0.01), pytest.raises(
            RuntimeError
        ) as exc_info:
            # WHEN
            adaptor.on_start()

        # THEN
        assert (
            str(exc_info.value)
            == "Could not find a socket because the server did not finish initializing"
        )

    @patch.object(adaptor_module.os.path, "isfile", return_value=False)
    def test_client_not_found(
        self,
        mock_isfile: Mock,
        init_data: dict,
    ) -> None:
        """Tests that the an error is raised if the nuke client file cannot be found"""
        # GIVEN
        adaptor = NukeAdaptor(init_data)
        test_dir = "test_dir"

        with patch.object(adaptor_module.sys, "path", ["unreported_dir", test_dir]):
            with pytest.raises(FileNotFoundError) as exc_info:
                # WHEN
                adaptor.nuke_client_path

        # THEN
        error_msg = (
            "Could not find nuke_client.py. Check that the NukeClient package is in "
            f"one of the following directories: {[test_dir]}"
        )
        assert str(exc_info.value) == error_msg
        mock_isfile.assert_called_with(
            os.path.join(test_dir, "deadline", "nuke_adaptor", "NukeClient", "nuke_client.py")
        )

    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.ActionsQueue.__len__", return_value=1)
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.LoggingSubprocess")
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.AdaptorServer")
    def test_nuke_init_timeout(
        self,
        mock_server: Mock,
        mock_logging_subprocess: Mock,
        mock_actions_queue: Mock,
        init_data: dict,
    ) -> None:
        """
        Tests that a TimeoutError is raised if the nuke client does not complete initialization
        tasks within a given time frame
        """
        # GIVEN
        adaptor = NukeAdaptor(init_data)
        mock_server.return_value.socket_path = "/tmp/9999"
        new_timeout = 0.01

        with patch.object(adaptor, "_NUKE_START_TIMEOUT_SECONDS", new_timeout), pytest.raises(
            TimeoutError
        ) as exc_info:
            # WHEN
            adaptor.on_start()

        # THEN
        error_msg = (
            f"Nuke did not complete initialization actions in {new_timeout} seconds and "
            "failed to start."
        )
        assert str(exc_info.value) == error_msg

    @patch.object(NukeAdaptor, "_nuke_is_running", False)
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.ActionsQueue.__len__", return_value=1)
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.LoggingSubprocess")
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.AdaptorServer")
    def test_nuke_init_fail(
        self,
        mock_server: Mock,
        mock_logging_subprocess: Mock,
        mock_actions_queue: Mock,
        init_data: dict,
    ) -> None:
        """
        Tests that an RuntimeError is raised if the nuke client encounters an exception
        """
        # GIVEN
        adaptor = NukeAdaptor(init_data)
        mock_server.return_value.socket_path = "/tmp/9999"

        with pytest.raises(RuntimeError) as exc_info:
            # WHEN
            adaptor.on_start()

        # THEN
        error_msg = "Nuke encountered an error and was not able to complete initialization actions."
        assert str(exc_info.value) == error_msg

    @patch.object(NukeAdaptor, "_action_queue")
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.LoggingSubprocess")
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.AdaptorServer")
    def test_populate_action_queue(
        self,
        mock_server: Mock,
        mock_logging_subprocess: Mock,
        mock_actions_queue: Mock,
        init_data: dict,
    ) -> None:
        """Tests that the action queue is populated correctly"""
        # GIVEN
        mock_actions_queue.__len__.return_value = 0
        adaptor = NukeAdaptor(init_data)
        mock_server.return_value.socket_path = "/tmp/9999"

        # WHEN
        adaptor.on_start()

        # THEN
        calls = mock_actions_queue.enqueue_action.call_args_list
        for _call, name in zip(calls[: len(_FIRST_NUKE_ACTIONS)], _FIRST_NUKE_ACTIONS):
            assert _call.args[0].name == name, f"Action: {name} missing from first actions"
        for _call, name in zip(
            calls[len(_FIRST_NUKE_ACTIONS) : len(_FIRST_NUKE_ACTIONS) + len(_NUKE_INIT_KEYS)],
            _NUKE_INIT_KEYS,
        ):
            assert _call.args[0].name == name, f"Action: {name} missing from init actions"

    @patch.object(NukeAdaptor, "_action_queue")
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.LoggingSubprocess")
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.AdaptorServer")
    def test_populate_action_queue_less_init_data(
        self,
        mock_server: Mock,
        mock_logging_subprocess: Mock,
        mock_actions_queue: Mock,
    ) -> None:
        """
        Tests that the action queue is populated correctly when not all keys are in the init data
        """
        # GIVEN
        init_data = {
            "script_file": "/path/to/some/nukescript.nk",
            "continue_on_error": True,
        }
        mock_actions_queue.__len__.return_value = 0
        adaptor = NukeAdaptor(init_data)
        mock_server.return_value.socket_path = "/tmp/9999"
        expected_action_names_queued = init_data.keys() & _NUKE_INIT_KEYS | set(_FIRST_NUKE_ACTIONS)

        # WHEN
        adaptor.on_start()

        # THEN
        calls = mock_actions_queue.enqueue_action.call_args_list
        assert len(calls) == len(expected_action_names_queued)
        for _call in calls:
            assert _call.args[0].name in expected_action_names_queued

    @patch.object(NukeAdaptor, "_nuke_is_running", False)
    def test_init_data_wrong_schema(
        self,
    ) -> None:
        """
        Tests that an RuntimeError is raised if the nuke client encounters an exception
        """
        # GIVEN
        init_data = {"doesNot": "conform", "thisData": "isBad"}
        adaptor = NukeAdaptor(init_data)

        with pytest.raises(jsonschema.exceptions.ValidationError) as exc_info:
            # WHEN
            adaptor.on_start()

        # THEN
        error_msg = " is a required property"
        assert error_msg in exc_info.value.message


class TestNukeAdaptor_on_run:
    @patch("time.sleep")
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.ActionsQueue.__len__", return_value=0)
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.LoggingSubprocess")
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.AdaptorServer")
    def test_on_run(
        self,
        mock_server: Mock,
        mock_logging_subprocess: Mock,
        mock_actions_queue: Mock,
        mock_sleep: Mock,
        init_data: dict,
        run_data: dict,
    ) -> None:
        """Tests that on_run waits for completion"""
        # GIVEN
        adaptor = NukeAdaptor(init_data)
        mock_server.return_value.socket_path = "/tmp/9999"
        # First side_effect value consumed by setter
        is_rendering_mock = PropertyMock(side_effect=[None, True, False])
        NukeAdaptor._is_rendering = is_rendering_mock
        adaptor.on_start()

        # WHEN
        adaptor.on_run(run_data)

        # THEN
        mock_sleep.assert_called_once_with(0.1)

    @patch("time.sleep")
    @patch(
        "deadline.nuke_adaptor.NukeAdaptor.adaptor.NukeAdaptor._is_rendering",
        new_callable=PropertyMock,
    )
    @patch(
        "deadline.nuke_adaptor.NukeAdaptor.adaptor.NukeAdaptor._nuke_is_running",
        new_callable=PropertyMock,
    )
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.ActionsQueue.__len__", return_value=0)
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.LoggingSubprocess")
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.AdaptorServer")
    def test_on_run_render_fail(
        self,
        mock_server: Mock,
        mock_logging_subprocess: Mock,
        mock_actions_queue: Mock,
        mock_nuke_is_running: Mock,
        mock_is_rendering: Mock,
        mock_sleep: Mock,
        init_data: dict,
        run_data: dict,
    ) -> None:
        """Tests that on_run raises an error if the render fails"""
        # GIVEN
        mock_is_rendering.side_effect = [None, True, False]
        mock_nuke_is_running.side_effect = [True, True, True, False, False]
        mock_logging_subprocess.return_value.returncode = 1
        adaptor = NukeAdaptor(init_data)
        mock_server.return_value.socket_path = "/tmp/9999"
        adaptor.on_start()

        # WHEN
        with pytest.raises(RuntimeError) as exc_info:
            adaptor.on_run(run_data)

        # THEN
        mock_sleep.assert_called_once_with(0.1)
        assert str(exc_info.value) == (
            "Nuke exited early and did not render successfully, please check render logs. "
            "Exit code 1"
        )

    @patch(
        "deadline.nuke_adaptor.NukeAdaptor.adaptor.NukeAdaptor._nuke_is_running",
        new_callable=PropertyMock,
    )
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.ActionsQueue.__len__", return_value=0)
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.LoggingSubprocess")
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.AdaptorServer")
    def test_run_data_wrong_schema(
        self,
        mock_server: Mock,
        mock_nuke_is_running: Mock,
        mock_logging_subprocess: Mock,
        mock_actions_queue: Mock,
        init_data: dict,
    ) -> None:
        """Tests that on_run waits for completion"""
        # GIVEN
        adaptor = NukeAdaptor(init_data)
        mock_server.return_value.socket_path = "/tmp/9999"
        # First side_effect value consumed by setter
        mock_nuke_is_running.side_effect = [True]
        run_data = {"bad": "schema"}

        with pytest.raises(jsonschema.exceptions.ValidationError) as exc_info:
            # WHEN
            adaptor.on_run(run_data)

        # THEN
        error_msg = " is a required property"
        assert error_msg in exc_info.value.message


class TestNukeAdaptor_on_stop:
    @patch("time.sleep")
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.ActionsQueue.__len__", return_value=0)
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.LoggingSubprocess")
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.AdaptorServer")
    def test_on_stop(
        self,
        mock_server: Mock,
        mock_logging_subprocess: Mock,
        mock_actions_queue: Mock,
        mock_sleep: Mock,
        init_data: dict,
        run_data: dict,
    ) -> None:
        # GIVEN
        adaptor = NukeAdaptor(init_data)
        mock_server.return_value.socket_path = "/tmp/9999"
        is_rendering_mock = PropertyMock(return_value=False)
        NukeAdaptor._is_rendering = is_rendering_mock
        adaptor.on_start()
        adaptor.on_run(run_data)

        try:
            # WHEN
            adaptor.on_stop()
        except Exception as e:
            pytest.fail(f"Test raised an exception when it shouldn't have: {e}")
        else:
            # THEN
            pass  # on_stop ran without exception


class TestNukeAdaptor_on_cleanup:
    @patch("time.sleep")
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor._logger")
    def test_on_cleanup_nuke_not_graceful_shutdown(
        self, mock_logger: Mock, mock_sleep: Mock, init_data: dict
    ) -> None:
        """Tests that on_cleanup reports when nuke does not gracefully shutdown"""
        # GIVEN
        adaptor = NukeAdaptor(init_data)

        with patch(
            "deadline.nuke_adaptor.NukeAdaptor.adaptor.NukeAdaptor._nuke_is_running",
            new_callable=lambda: True,
        ), patch.object(adaptor, "_NUKE_END_TIMEOUT_SECONDS", 0.01), patch.object(
            adaptor, "_nuke_client"
        ) as mock_client:
            # WHEN
            adaptor.on_cleanup()

        # THEN
        mock_logger.error.assert_called_once_with(
            "Nuke did not complete cleanup actions and failed to gracefully shutdown. Terminating."
        )
        mock_client.terminate.assert_called_once()

    @patch("time.sleep")
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor._logger")
    def test_on_cleanup_server_not_graceful_shutdown(
        self, mock_logger: Mock, mock_sleep: Mock, init_data: dict
    ) -> None:
        """Tests that on_cleanup reports when the server does not shutdown"""
        # GIVEN
        adaptor = NukeAdaptor(init_data)

        with patch(
            "deadline.nuke_adaptor.NukeAdaptor.adaptor.NukeAdaptor._nuke_is_running",
            new_callable=lambda: False,
        ), patch.object(adaptor, "_SERVER_END_TIMEOUT_SECONDS", 0.01), patch.object(
            adaptor, "_server_thread"
        ) as mock_server_thread:
            mock_server_thread.is_alive.return_value = True
            # WHEN
            adaptor.on_cleanup()

        # THEN
        mock_logger.error.assert_called_once_with("Failed to shutdown the Nuke Adaptor server.")
        mock_server_thread.join.assert_called_once_with(timeout=0.01)

    @patch("time.sleep")
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.ActionsQueue.__len__", return_value=0)
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.LoggingSubprocess")
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.AdaptorServer")
    def test_on_cleanup(
        self,
        mock_server: Mock,
        mock_logging_subprocess: Mock,
        mock_actions_queue: Mock,
        mock_sleep: Mock,
        init_data: dict,
        run_data: dict,
    ) -> None:
        # GIVEN
        adaptor = NukeAdaptor(init_data)
        mock_server.return_value.socket_path = "/tmp/9999"
        is_rendering_mock = PropertyMock(return_value=False)
        NukeAdaptor._is_rendering = is_rendering_mock

        adaptor.on_start()
        adaptor.on_run(run_data)
        adaptor.on_stop()

        with patch(
            "deadline.nuke_adaptor.NukeAdaptor.adaptor.NukeAdaptor._nuke_is_running",
            new_callable=lambda: False,
        ):
            # WHEN
            adaptor.on_cleanup()

        # THEN
        return  # Assert no errors occured

    def test_regex_callbacks_cache(self, init_data):
        """Test that regex callbacks are generated exactly once"""
        # GIVEN
        adaptor = NukeAdaptor(init_data)

        # WHEN
        regex_callbacks = adaptor.regex_callbacks

        # THEN
        assert regex_callbacks is adaptor.regex_callbacks

    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.NukeAdaptor.update_status")
    def test_handle_complete(self, mock_update_status: Mock, init_data: dict):
        """Tests that the _handle_complete method updates the progress correctly"""
        # GIVEN
        adaptor = NukeAdaptor(init_data)
        regex_callbacks = adaptor.regex_callbacks
        complete_regex = regex_callbacks[0].regex_list[0]

        # WHEN
        match = complete_regex.search("NukeClient: Finished Rendering Frame 1")
        if match:
            adaptor._handle_complete(match)

        # THEN
        assert match is not None
        mock_update_status.assert_called_once_with(progress=100, status_message="RENDER COMPLETE")

    handle_progess_params = [
        (
            (1, 2),
            (
                "NukeClient: Creating outputs 0-1 of 10 total outputs.",
                "Writing output/path.exr took 0.44 seconds",
            ),
            (0.0, 10.0),
        ),
        (
            (1, 2),
            (
                "NukeClient: Creating outputs 4-8 of 10 total outputs.",
                "Writing output/path.exr took 0.99 seconds",
            ),
            (40.0, 50.0),
        ),
    ]

    @pytest.mark.parametrize("regex_index, stdout, expected_progress", handle_progess_params)
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.NukeAdaptor.update_status")
    @patch.object(NukeAdaptor, "_is_rendering", new_callable=PropertyMock(return_value=True))
    def test_handle_progress(
        self,
        mock_is_rendering: Mock,
        mock_update_status: Mock,
        regex_index: tuple[int, int],
        stdout: tuple[str, str],
        expected_progress: tuple[float, float],
        init_data: dict,
    ) -> None:
        # GIVEN
        adaptor = NukeAdaptor(init_data)
        regex_callbacks = adaptor.regex_callbacks
        progress_index, output_complete_index = regex_index
        progress_regex = regex_callbacks[progress_index].regex_list[0]
        output_complete_regex = regex_callbacks[output_complete_index].regex_list[0]

        # WHEN
        if progress_match := progress_regex.search(stdout[0]):
            adaptor._handle_progress(progress_match)
        if output_complete_match := output_complete_regex.search(stdout[1]):
            adaptor._handle_output_complete(output_complete_match)

        # THEN
        assert progress_match is not None
        assert output_complete_match is not None
        mock_update_status.assert_has_calls(
            [call(progress=progress) for progress in expected_progress]
        )

    handle_error_params = [
        ("ERROR: Something terrible happened", 0),
        ("Error: Something terrible happened", 1),
        ("Error : Something terrible happened", 2),
        ("Eddy[ERROR] - Something terrible happened", 3),
    ]

    @pytest.mark.parametrize("continue_on_error", [True, False])
    @pytest.mark.parametrize("stdout, regex_index", handle_error_params)
    @patch("deadline.nuke_adaptor.NukeAdaptor.adaptor.NukeAdaptor.update_status")
    @patch.object(NukeAdaptor, "_is_rendering", new_callable=PropertyMock(return_value=True))
    def test_handle_error(
        self,
        mock_is_rendering: Mock,
        mock_update_status: Mock,
        stdout: str,
        regex_index: int,
        continue_on_error: bool,
        init_data: dict,
    ) -> None:
        # GIVEN
        ERROR_CALLBACK_INDEX = 3
        init_data["continue_on_error"] = continue_on_error
        adaptor = NukeAdaptor(init_data)
        regex_callbacks = adaptor.regex_callbacks
        error_regex = regex_callbacks[ERROR_CALLBACK_INDEX].regex_list[regex_index]

        if match := error_regex.search(stdout):
            # WHEN
            adaptor._handle_error(match)

        # THEN
        assert match
        if continue_on_error:
            assert adaptor._exc_info is None
        else:
            assert isinstance(adaptor._exc_info, RuntimeError)
            assert str(adaptor._exc_info) == f"Nuke Encountered an Error: {stdout}"

    @pytest.mark.parametrize("adaptor_exc_info", [RuntimeError("Something Bad Happened!"), None])
    def test_has_exception(self, init_data: dict, adaptor_exc_info: Exception | None) -> None:
        """
        Validates that the adaptor._has_exception property raises when adaptor._exc_info is not None
        and returns false when adaptor._exc_info is None
        """
        adaptor = NukeAdaptor(init_data)
        adaptor._exc_info = adaptor_exc_info

        if adaptor_exc_info:
            with pytest.raises(RuntimeError) as exc_info:
                adaptor._has_exception

            assert exc_info.value == adaptor_exc_info
        else:
            assert not adaptor._has_exception

    @patch.object(NukeAdaptor, "_nuke_is_running", new_callable=PropertyMock(return_value=False))
    def test_raises_if_nuke_not_running(
        self,
        init_data: dict,
        run_data: dict,
    ) -> None:
        """Tests that on_run raises a NukeNotRunningError if nuke is not running"""
        # GIVEN
        adaptor = NukeAdaptor(init_data)

        # WHEN
        with pytest.raises(NukeNotRunningError) as raised_err:
            adaptor.on_run(run_data)

        # THEN
        assert raised_err.match("Cannot render because Nuke is not running.")


class TestNukeAdaptor_on_cancel:
    """Tests for NukeAdaptor.on_cancel"""

    def test_terminates_nuke_client(self, init_data: dict, caplog: pytest.LogCaptureFixture):
        # GIVEN
        caplog.set_level(0)
        adaptor = NukeAdaptor(init_data)
        adaptor._nuke_client = mock_client = Mock()

        # WHEN
        adaptor.on_cancel()

        # THEN
        mock_client.terminate.assert_called_once_with(grace_time_s=0)
        assert "CANCEL REQUESTED" in caplog.text

    def test_does_nothing_if_nuke_not_running(
        self, init_data: dict, caplog: pytest.LogCaptureFixture
    ):
        """Tests that nothing happens if a cancel is requested when nuke is not running"""
        # GIVEN
        caplog.set_level(0)
        adaptor = NukeAdaptor(init_data)
        adaptor._nuke_client = None

        # WHEN
        adaptor.on_cancel()

        # THEN
        assert "CANCEL REQUESTED" in caplog.text
        assert "Nothing to cancel because Nuke is not running" in caplog.text
