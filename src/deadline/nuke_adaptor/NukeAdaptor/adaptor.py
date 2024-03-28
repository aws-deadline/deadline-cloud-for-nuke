# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

import logging
import os
import re
import sys
import threading
import time
import jsonschema  # type: ignore
from typing import Callable, cast

from deadline.client.api import get_deadline_cloud_library_telemetry_client, TelemetryClient
from openjd.adaptor_runtime._version import version as openjd_adaptor_version
from openjd.adaptor_runtime.adaptors import Adaptor, AdaptorDataValidators, SemanticVersion
from openjd.adaptor_runtime_client import Action
from openjd.adaptor_runtime.process import LoggingSubprocess
from openjd.adaptor_runtime.app_handlers import RegexCallback, RegexHandler
from openjd.adaptor_runtime.application_ipc import ActionsQueue, AdaptorServer

from .._version import version as adaptor_version

_logger = logging.getLogger(__name__)


class NukeNotRunningError(Exception):
    """Error that is raised when attempting to use Nuke while it is not running"""

    pass


# Actions which must be queued before any others
_FIRST_NUKE_ACTIONS = ["script_file"]
_NUKE_INIT_KEYS = {
    "continue_on_error",
    "proxy",
    "write_nodes",
    "views",
}


def _check_for_exception(func: Callable) -> Callable:
    """
    Decorator that checks if an exception has been caught before calling the
    decorated function
    """

    def wrapped_func(self, *args, **kwargs):
        if not self._has_exception:  # Raises if there is an exception  # pragma: no branch
            return func(self, *args, **kwargs)

    return wrapped_func


class NukeAdaptor(Adaptor):
    """
    Adaptor that creates a session in Nuke to Render interactively.
    """

    _SERVER_START_TIMEOUT_SECONDS = 30
    _SERVER_END_TIMEOUT_SECONDS = 30
    _NUKE_START_TIMEOUT_SECONDS = 300
    _NUKE_END_TIMEOUT_SECONDS = 30

    _server: AdaptorServer | None = None
    _server_thread: threading.Thread | None = None
    _nuke_client: LoggingSubprocess | None = None
    _action_queue = ActionsQueue()
    _is_rendering: bool = False
    # If a thread raises an exception we will update this to raise in the main thread
    _exc_info: Exception | None = None
    _performing_cleanup = False
    _regex_callbacks: list | None = None
    _validators: AdaptorDataValidators | None = None
    _telemetry_client: TelemetryClient | None = None

    # Output tracking for progress handling
    _curr_output: int = 1
    _total_outputs: int = 1
    _nuke_version: str = ""

    @property
    def integration_data_interface_version(self) -> SemanticVersion:
        return SemanticVersion(major=0, minor=1)

    @staticmethod
    def _get_timer(timeout: int | float) -> Callable[[], bool]:
        """Given a timeout length, returns a lambda which returns False until the timeout occurs"""
        timeout_time = time.time() + timeout
        return lambda: time.time() >= timeout_time

    @property
    def _has_exception(self) -> bool:
        """Property which checks the private _exc_info property for an exception

        Raises:
            self._exc_info: An exception if there is one

        Returns:
            bool: False there is no exception waiting to be raised
        """
        if self._exc_info and not self._performing_cleanup:
            raise self._exc_info
        return False

    @property
    def continue_on_error(self) -> bool:
        """Property which returns whether to continue on errors or not

        Returns:
            bool: True if the behavior is to continue on errors. False otherwise.
        """
        return cast(bool, self.init_data.get("continue_on_error", True))

    @property
    def _nuke_is_running(self) -> bool:
        """Property which indicates that the nuke client is running

        Returns:
            bool: True if the nuke client is running, false otherwise
        """
        return self._nuke_client is not None and self._nuke_client.is_running

    @property
    def progress(self) -> float:
        """
        Property which calculates progress based on the number of outputs
        reported and the total outputs expected

        Returns:
            float: The calculated progress
        """
        return max(min(round(100.0 * self._curr_output / self._total_outputs, 2), 100), 0)

    @property
    def validators(self) -> AdaptorDataValidators:
        if not self._validators:
            cur_dir = os.path.dirname(__file__)
            schema_dir = os.path.join(cur_dir, "schemas")
            self._validators = AdaptorDataValidators.for_adaptor(schema_dir)
        return self._validators

    @property
    def regex_callbacks(self) -> list[RegexCallback]:
        """
        Returns a list of RegexCallbacks used by the Nuke Adaptor

        Returns:
            list[RegexCallback]: List of Regex Callbacks to add
        """
        if not self._regex_callbacks:
            callback_list = []
            completed_regexes = [
                re.compile("NukeClient: Finished Rendering Frame [0-9]+"),
                re.compile("NukeClient: Finished Rendering Frames [0-9]+-[0-9]+"),
            ]
            progress_regexes = [
                re.compile(
                    "NukeClient: Creating outputs ([0-9]+)-([0-9]+) of ([0-9]+) total outputs."
                ),
            ]
            error_regexes = [
                re.compile(".*ERROR:.*"),
                re.compile(".*Error:.*"),
                re.compile(".*Error :.*"),
                re.compile(".*Eddy\\[ERROR\\].*"),
            ]
            # Capture the major minor group (ie. 15.0), patch version (ie. v1) is an optional subgroup.
            version_regexes = [re.compile("NukeClient: Nuke Version ([0-9]+.[0-9]+)(v[0-9]+)?")]
            output_complete_regexes = [re.compile(r"Writing .+ took [0-9\.]+ seconds")]
            callback_list.append(RegexCallback(completed_regexes, self._handle_complete))
            callback_list.append(RegexCallback(progress_regexes, self._handle_progress))
            callback_list.append(
                RegexCallback(output_complete_regexes, self._handle_output_complete)
            )
            callback_list.append(RegexCallback(error_regexes, self._handle_error))
            callback_list.append(RegexCallback(version_regexes, self._handle_version))
            self._regex_callbacks = callback_list
        return self._regex_callbacks

    @_check_for_exception
    def _handle_complete(self, match: re.Match) -> None:
        """
        Callback for stdout that indicates completeness of a render. Updates progress to 100
        Args:
            match (re.Match): The match object from the regex pattern that was matched the message
        """
        self._is_rendering = False
        self.update_status(progress=100, status_message="RENDER COMPLETE")

    @_check_for_exception
    def _handle_progress(self, match: re.Match) -> None:
        """
        Callback for stdout that indicates progress of a render.
        Args:
            match (re.Match): The match object from the regex pattern that was matched the message
        """
        self._curr_output = int(match.groups()[0])
        self._total_outputs = int(match.groups()[2])
        self.update_status(progress=self.progress)

    @_check_for_exception
    def _handle_output_complete(self, match: re.Match) -> None:
        """
        Callback for stdout that indicates an outpout has been created.
        Args:
            match (re.Match): The match object from the regex pattern that was matched the message
        """
        self._curr_output += 1
        if self._is_rendering:
            self.update_status(progress=self.progress)

    def _handle_error(self, match: re.Match) -> None:
        """
        Callback for stdout that indicates an error or warning. Sets the private _exc_info variable
        which will be raised in the main thread.

        Args:
            match (re.Match): The match object from the regex pattern that was matched the message
        """
        if not self.continue_on_error:
            self._exc_info = RuntimeError(f"Nuke Encountered an Error: {match.group(0)}")

    def _handle_version(self, match: re.Match) -> None:
        """
        Callback for stdout that records the Nuke version.
        Args:
            match (re.Match): The match object from the regex pattern that was matched the message
        """
        self._nuke_version = match.groups()[0]
        if len(match.groups()) > 1 and match.groups()[1]:
            self._nuke_version += match.groups()[1]

    @property
    def server_server_path(self) -> str:
        """
        Performs a busy wait for the socket path that the adaptor server is running on, then returns
        it.

        Raises:
            RuntimeError: If the server does not finish initializing

        Returns:
            str: The socket path the adaptor server is running on.
        """
        is_timed_out = self._get_timer(self._SERVER_START_TIMEOUT_SECONDS)
        while (self._server is None or self._server.server_path is None) and not is_timed_out():
            time.sleep(0.01)

        if self._server is not None and self._server.server_path is not None:
            return self._server.server_path

        raise RuntimeError("Could not find a socket because the server did not finish initializing")

    @property
    def nuke_client_path(self) -> str:
        """
        Obtains the nuke_client.py path by searching directories in sys.path

        Raises:
            FileNotFoundError: If the nuke_client.py file could not be found.

        Returns:
            str: The path to the nuke_client.py file.
        """
        for dir_ in sys.path:
            path = os.path.join(dir_, "deadline", "nuke_adaptor", "NukeClient", "nuke_client.py")
            if os.path.isfile(path):
                return path
        raise FileNotFoundError(
            "Could not find nuke_client.py. Check that the NukeClient package is in one of the "
            f"following directories: {sys.path[1:]}"
        )

    def on_start(self) -> None:
        """
        Initializes Nuke for job stickiness by starting Nuke, establishing IPC, and initializing the
        Nuke environment with the given Nuke script and any other init data.

        Raises:
            jsonschema.ValidationError: When init_data fails validation against the adaptor schema.
            jsonschema.SchemaError: When the adaptor schema itself is nonvalid.
            RuntimeError: If Nuke did not complete initialization actions due to an exception
            TimeoutError: If Nuke did not complete initialization actions due to timing out.
            FileNotFoundError: If the nuke_client.py file could not be found.
            KeyError: If a configuration for the given platform and version does not exist.
        """
        self.validators.init_data.validate(self.init_data)

        self.update_status(progress=0, status_message="Initializing Nuke")
        self._server_thread = self._start_nuke_server_thread()
        self._populate_action_queue()

        self._start_nuke_client()

        is_timed_out = self._get_timer(self._NUKE_START_TIMEOUT_SECONDS)
        while self._nuke_is_running and not self._has_exception and len(self._action_queue) > 0:
            if is_timed_out():
                raise TimeoutError(
                    "Nuke did not complete initialization actions in "
                    f"{self._NUKE_START_TIMEOUT_SECONDS} seconds and failed to start."
                )

            time.sleep(0.1)  # busy wait for nuke to finish initialization

        self._get_deadline_telemetry_client().record_event(
            event_type="com.amazon.rum.deadline.adaptor.runtime.start", event_details={}
        )

        if len(self._action_queue) > 0:
            raise RuntimeError(
                "Nuke encountered an error and was not able to complete initialization actions."
            )

    def on_run(self, run_data: dict) -> None:
        """
        This starts a render in Nuke for the given frame and performs a busy wait until the render
        completes.
        """
        if not self._nuke_is_running:
            raise NukeNotRunningError("Cannot render because Nuke is not running.")

        if "frameRange" not in run_data and "frame" not in run_data:
            raise jsonschema.exceptions.ValidationError(
                "Cannot run Nuke adaptor. 'frame' or 'frameRange' is a required property."
            )

        self.validators.run_data.validate(run_data)
        self._is_rendering = True

        self._action_queue.enqueue_action(
            Action(
                "start_render",
                {"frameRange": run_data.get("frameRange", str(run_data.get("frame", "")))},
            )
        )

        while self._nuke_is_running and self._is_rendering and not self._has_exception:
            time.sleep(0.1)  # busy wait so that on_cleanup is not called

        if not self._nuke_is_running and self._nuke_client:  # Nuke Client will always exist here.
            #  This is always an error case because the Nuke Client should still be running and
            #  waiting for the next command. If the thread finished, then we cannot continue
            exit_code = self._nuke_client.returncode

            self._get_deadline_telemetry_client().record_error(
                {"exit_code": exit_code, "exception_scope": "on_run"}, str(RuntimeError)
            )
            raise RuntimeError(
                "Nuke exited early and did not render successfully, please check render logs. "
                f"Exit code {exit_code}"
            )

    def on_stop(self) -> None:
        """
        No action needed but this function must be implemented
        """
        return

    def on_cleanup(self):
        """
        Cleans up the adaptor by closing the nuke client and adaptor server.
        """
        self._performing_cleanup = True

        self._action_queue.enqueue_action(Action("close"), front=True)
        is_timed_out = self._get_timer(self._NUKE_END_TIMEOUT_SECONDS)
        while self._nuke_is_running and not is_timed_out():
            time.sleep(0.1)
        if self._nuke_is_running and self._nuke_client:
            _logger.error(
                "Nuke did not complete cleanup actions and failed to gracefully shutdown. "
                "Terminating."
            )
            self._nuke_client.terminate()

        if self._server:
            self._server.shutdown()

        if self._server_thread and self._server_thread.is_alive():
            self._server_thread.join(timeout=self._SERVER_END_TIMEOUT_SECONDS)
            if self._server_thread.is_alive():
                _logger.error("Failed to shutdown the Nuke Adaptor server.")

        self._performing_cleanup = False

    def on_cancel(self):
        """
        Cancels the current render if Nuke is rendering.
        """
        _logger.info("CANCEL REQUESTED")
        if not self._nuke_client or not self._nuke_is_running:
            _logger.info("Nothing to cancel because Nuke is not running")
            return

        # Terminate immediately since the Nuke client does not have a graceful shutdown
        self._nuke_client.terminate(grace_time_s=0)

    def _start_nuke_server_thread(self) -> threading.Thread:
        """
        Starts the nuke adaptor server in a thread.
        Sets the environment variable "NUKE_ADAPTOR_SERVER_PATH" to the socket the server is running
        on after the server has finished starting.

        Returns:
            threading.Thread: The thread in which the server is running
        """

        def start_nuke_server() -> None:
            """
            Starts a server with the given ActionsQueue, attaches the server to the adaptor and
            serves forever in a blocking call.
            """
            self._server = AdaptorServer(self._action_queue, self)
            self._server.serve_forever()

        server_thread = threading.Thread(target=start_nuke_server)
        server_thread.start()
        os.environ["NUKE_ADAPTOR_SERVER_PATH"] = self.server_server_path

        return server_thread

    def _start_nuke_client(self) -> None:
        """
        Starts the nuke client by launching Nuke with the nuke_client.py file and the generated
        arguments.

        Nuke must be on the system PATH, for example due to a Rez environment being active.

        Raises:
            FileNotFoundError: If the nuke_client.py file could not be found.
            KeyError: If a configuration for the given platform and version does not exist.
        """
        nuke_exe = os.environ.get("NUKE_ADAPTOR_NUKE_EXECUTABLE", "nuke")
        regexhandler = RegexHandler(self.regex_callbacks)

        # Add the Open Job Description namespace directory to PYTHONPATH, so that adaptor_runtime_client
        # will be available directly to the nuke client.
        import openjd.adaptor_runtime_client
        import deadline.nuke_adaptor
        import deadline.nuke_util

        openjd_namespace_dir = os.path.dirname(
            os.path.dirname(openjd.adaptor_runtime_client.__file__)
        )
        deadline_adaptor_namespace_dir = os.path.dirname(
            os.path.dirname(deadline.nuke_adaptor.__file__)
        )
        deadline_util_namespace_dir = os.path.dirname(os.path.dirname(deadline.nuke_util.__file__))
        python_path_addition = f"{openjd_namespace_dir}{os.pathsep}{deadline_adaptor_namespace_dir}{os.pathsep}{deadline_util_namespace_dir}"
        if "PYTHONPATH" in os.environ:
            os.environ["PYTHONPATH"] = (
                f"{os.environ['PYTHONPATH']}{os.pathsep}{python_path_addition}"
            )
        else:
            os.environ["PYTHONPATH"] = python_path_addition

        self._nuke_client = LoggingSubprocess(
            args=[nuke_exe, "-V", "2", "-t", self.nuke_client_path],
            stdout_handler=regexhandler,
            stderr_handler=regexhandler,
        )

    def _populate_action_queue(self) -> None:
        """
        Populates the adaptor server's action queue with actions from the init_data that the Nuke
        Client will request and perform. The action must be present in the _FIRST_NUKE_ACTIONS or
        _NUKE_INIT_KEYS set to be added to the action queue.
        """
        for name in _FIRST_NUKE_ACTIONS:
            self._action_queue.enqueue_action(Action(name, {name: self.init_data[name]}))

        for name in _NUKE_INIT_KEYS:
            if name in self.init_data:
                self._action_queue.enqueue_action(Action(name, {name: self.init_data[name]}))

    def _get_deadline_telemetry_client(self):
        """
        Wrapper around the Deadline Client Library telemetry client, in order to set package-specific information
        """
        if not self._telemetry_client:
            self._telemetry_client = get_deadline_cloud_library_telemetry_client()
            self._telemetry_client.update_common_details(
                {
                    "deadline-cloud-for-nuke-adaptor-version": adaptor_version,
                    "nuke-version": self._nuke_version,
                    "open-jd-adaptor-runtime-version": openjd_adaptor_version,
                }
            )
        return self._telemetry_client
