# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import os
import tempfile
from pathlib import PurePosixPath, PureWindowsPath
from typing import (
    List,
    Type,
)
from unittest.mock import Mock, patch
from test.unit.mock_stubs import MockOCIOConfig

import nuke
import pytest
from openjd.adaptor_runtime_client import (
    ClientInterface,
    PathMappingRule,
)

import deadline.nuke_adaptor.NukeClient.nuke_client as nuke_client_mod
from deadline.nuke_adaptor.NukeClient.nuke_client import NukeClient, main


class TestNukeClient:
    @patch.object(nuke_client_mod, "NukeHandler")
    def test_nukeclient(self, mock_handler) -> None:
        """Tests that the nuke client can initialize, set actions and close"""
        # GIVEN
        handler_action_dict = {f"action{i}": lambda: None for i in range(10)}
        mock_handler.return_value.action_dict = handler_action_dict

        # WHEN
        client = NukeClient(server_path="/tmp/9999")

        # THEN
        mock_handler.assert_called_once()
        assert handler_action_dict.items() <= client.actions.items()

    @patch("deadline.nuke_adaptor.NukeClient.nuke_client.os.path.exists")
    @patch.dict(os.environ, {"NUKE_ADAPTOR_SERVER_PATH": "9999"})
    @patch("deadline.nuke_adaptor.NukeClient.NukeClient.poll")
    @patch("deadline.nuke_adaptor.NukeClient.nuke_client._ClientInterface")
    def test_main(self, mock_client: Mock, mock_poll: Mock, mock_exists: Mock) -> None:
        """Tests that the main method starts the nuke client polling method"""
        # GIVEN
        mock_exists.return_value = True

        # WHEN
        main()

        # THEN
        mock_exists.assert_called_once_with("9999")
        mock_poll.assert_called_once()

    @patch.dict(os.environ, {}, clear=True)
    @patch("deadline.nuke_adaptor.NukeClient.NukeClient.poll")
    def test_main_no_server_socket(self, mock_poll: Mock) -> None:
        """Tests that the main method raises an OSError if no server socket is found"""
        # WHEN
        with pytest.raises(OSError) as exc_info:
            main()

        # THEN
        assert str(exc_info.value) == (
            "NukeClient cannot connect to the Adaptor because the environment variable "
            "NUKE_ADAPTOR_SERVER_PATH does not exist"
        )
        mock_poll.assert_not_called()

    @patch("deadline.nuke_adaptor.NukeClient.nuke_client.os.path.exists")
    @patch.dict(os.environ, {"NUKE_ADAPTOR_SERVER_PATH": "/a/path/that/does/not/exist"})
    @patch("deadline.nuke_adaptor.NukeClient.NukeClient.poll")
    def test_main_server_socket_not_exist(self, mock_poll: Mock, mock_exists: Mock) -> None:
        """Tests that the main method raises an OSError if the server socket does not exist"""
        # GIVEN
        mock_exists.return_value = False

        # WHEN
        with pytest.raises(OSError) as exc_info:
            main()

        # THEN
        mock_exists.assert_called_once_with("/a/path/that/does/not/exist")
        assert str(exc_info.value) == (
            "NukeClient cannot connect to the Adaptor because the socket at the path defined by "
            "the environment variable NUKE_ADAPTOR_SERVER_PATH does not exist. Got: "
            f"{os.environ['NUKE_ADAPTOR_SERVER_PATH']}"
        )
        mock_poll.assert_not_called()

    @patch.object(nuke, "scriptExit")
    @patch.object(nuke, "scriptClose")
    def test_close(self, mock_script_close: Mock, mock_script_exit: Mock):
        """
        Test that nuke closes and exits on client.close()
        """
        # GIVEN
        client = NukeClient(server_path="/tmp/9999")

        # WHEN
        client.close()

        # THEN
        mock_script_close.assert_called_once_with()
        mock_script_exit.assert_called_once_with()

    @patch.object(nuke, "scriptExit")
    @patch.object(nuke, "scriptClose")
    def test_graceful_shutdown(self, mock_script_close: Mock, mock_script_exit: Mock):
        """
        Test that nuke closes and exits on client.graceful_shutdown
        """
        # GIVEN
        client = NukeClient(server_path="/tmp/9999")

        # WHEN
        client.graceful_shutdown(1, Mock())

        # THEN
        mock_script_close.assert_called_once_with()
        mock_script_exit.assert_called_once_with()

    @pytest.mark.parametrize("is_dir", [True, False])
    @patch.object(nuke_client_mod, "os")
    def test_ensure_output_dir(self, mock_os: Mock, is_dir: bool):
        """
        Test that the ensure_output_dir handle which is run before each render works properly
        """
        # GIVEN
        NukeClient(server_path="/tmp/9999")
        mock_os.path.isdir.return_value = is_dir
        ensure_output_dir = nuke.addBeforeRender.call_args[0][0]

        # WHEN
        ensure_output_dir()

        # THEN
        mock_os.path.isdir.assert_called_once_with(mock_os.path.dirname.return_value)
        if is_dir:
            mock_os.makedirs.assert_not_called()
        else:
            mock_os.makedirs.assert_called_once_with(mock_os.path.dirname.return_value)

    @pytest.mark.skipif(os.name == "nt", reason="POSIX path mapping not implemented on Windows")
    @pytest.mark.parametrize(
        "path, client_mapped, expected_mapped, new_path_class, rules",
        [
            (
                "some/path",
                "C:\\Some\\Windows\\Path",
                "C:/Some/Windows/Path",
                PureWindowsPath,
                [
                    PathMappingRule(
                        source_path_format="windows",
                        source_path="some",
                        destination_os="Windows",
                        destination_path="C:/Some",
                    ),
                ],
            ),
            (
                "some/path",
                "/some/linux/path/with\\ spaces",
                "/some/linux/path/with\\ spaces",
                PurePosixPath,
                [
                    PathMappingRule(
                        source_path_format="posix",
                        source_path="some",
                        destination_os="linux",
                        destination_path="/some/linux",
                    ),
                ],
            ),
        ],
    )
    @patch.object(nuke, "addFilenameFilter")
    @patch.object(nuke_client_mod, "Path")
    @patch.object(ClientInterface, "map_path")
    @patch.object(ClientInterface, "path_mapping_rules")
    def test_map_path(
        self,
        mock_path_mapping_rules: Mock,
        mock_map_path: Mock,
        mocked_path_class: Mock,
        mock_addfilenamefilter: Mock,
        path: str,
        client_mapped: str,
        expected_mapped: str,
        new_path_class: Type,
        rules: List[PathMappingRule],
    ):
        # GIVEN
        mocked_path_class.side_effect = new_path_class
        client = NukeClient(server_path="/tmp/9999")
        mock_map_path.return_value = client_mapped
        mock_path_mapping_rules.return_value = rules

        # WHEN
        mapped = client.map_path(path)

        # THEN
        mock_addfilenamefilter.assert_called_once_with(client.map_path)
        assert mapped == expected_mapped

    @pytest.mark.parametrize(
        "path, client_mapped, expected_mapped, new_path_class, rules",
        [
            (
                "/session-dir/thing",
                "/session-dir/session-dir/thing",
                "/session-dir/thing",
                PurePosixPath,
                [
                    PathMappingRule(
                        source_path_format="posix",
                        source_path="/",
                        destination_os="linux",
                        destination_path="/session-dir",
                    ),
                ],
            ),
            (
                "path/session-dir/thing",
                "path/session-dir/session-dir/thing",
                "path/session-dir/thing",
                PurePosixPath,
                [
                    PathMappingRule(
                        source_path_format="windows",
                        source_path="some",
                        destination_os="Windows",
                        destination_path="C:/Some",
                    ),
                    PathMappingRule(
                        source_path_format="posix",
                        source_path="path",
                        destination_os="linux",
                        destination_path="path/session-dir",
                    ),
                ],
            ),
        ],
        ids=["mapping from root", "multi-rule"],
    )
    @patch.object(nuke, "addFilenameFilter")
    @patch.object(nuke_client_mod, "Path")
    @patch.object(ClientInterface, "map_path")
    @patch.object(ClientInterface, "path_mapping_rules")
    def test_recursive_map_path(
        self,
        mock_path_mapping_rules: Mock,
        mock_map_path: Mock,
        mocked_path_class: Mock,
        mock_addfilenamefilter: Mock,
        path: str,
        client_mapped: str,
        expected_mapped: str,
        new_path_class: Type,
        rules: List[PathMappingRule],
    ):
        # GIVEN
        mocked_path_class.side_effect = new_path_class
        client = NukeClient(server_path="/tmp/9999")
        mock_map_path.return_value = client_mapped
        mock_path_mapping_rules.return_value = rules

        # WHEN
        mapped = client.map_path(path)

        # THEN
        mock_addfilenamefilter.assert_called_once_with(client.map_path)
        assert mapped == expected_mapped

    @pytest.mark.skipif(os.name == "nt", reason="POSIX path mapping not implemented on Windows")
    @patch.dict(os.environ, {"NUKE_TEMP_DIR": "/var/tmp/nuke_temp_dir"})
    @patch(
        "deadline.nuke_util.ocio.get_ocio_config_path",
        return_value="/session-dir/ocio/custom_config.ocio",
    )
    @patch(
        "deadline.nuke_util.ocio.create_config_from_file",
        return_value=MockOCIOConfig(
            working_dir="/session-dir/ocio", search_paths=["luts", "/absolute/path/to/luts"]
        ),
    )
    @patch("deadline.nuke_util.ocio.set_custom_config_path")
    def test_map_ocio_config(
        self,
        mock_set_custom_config_path: Mock,
        mock_create_config_from_file: Mock,
        mock_get_custom_config_path: Mock,
    ):
        # GIVEN
        def map_path(path: str):
            paths = {"/absolute/path/to/luts": "/session-dir/absolute/path/to/luts"}
            return paths.get(path, path)

        with patch.object(NukeClient, "map_path", wraps=map_path):
            expected_updated_search_paths = [
                "/session-dir/ocio/luts",
                "/session-dir/absolute/path/to/luts",
            ]

            expected_updated_config_path = os.path.join(
                os.environ["NUKE_TEMP_DIR"],
                os.path.basename(mock_get_custom_config_path.return_value),
            )

            temp_socket_file = tempfile.TemporaryFile()
            client = NukeClient(server_path=temp_socket_file.name)

            # WHEN
            client._map_ocio_config()

            actual_updated_search_paths = mock_create_config_from_file.return_value.getSearchPaths()

            actual_updated_config_path = mock_create_config_from_file.return_value._serialize_path

            # THEN
            assert expected_updated_search_paths == actual_updated_search_paths

            assert expected_updated_config_path == actual_updated_config_path

            mock_set_custom_config_path.assert_called_once_with(expected_updated_config_path)
