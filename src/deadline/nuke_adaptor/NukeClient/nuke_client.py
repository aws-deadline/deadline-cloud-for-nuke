# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path, PurePath
from types import FrameType as FrameType
from typing import (
    List,
    Optional,
)

# The Nuke Adaptor adds the `openjd` namespace directory to PYTHONPATH,
# so that importing just the adaptor_runtime_client should work.
try:
    from adaptor_runtime_client import (  # type: ignore[import]
        ClientInterface as _ClientInterface,
        PathMappingRule,
    )
    from nuke_adaptor.NukeClient.nuke_handler import NukeHandler  # type: ignore[import]
except ImportError:
    from openjd.adaptor_runtime_client import (
        ClientInterface as _ClientInterface,
        PathMappingRule,
    )
    from deadline.nuke_adaptor.NukeClient.nuke_handler import NukeHandler

try:
    import nuke
except ImportError:  # pragma: no cover
    raise OSError("Could not find the Nuke module. Are you running this inside of Nuke?")

try:
    from nuke_util import ocio as nuke_ocio  # type: ignore[import]
except ImportError:
    from deadline.nuke_util import ocio as nuke_ocio


class NukeClient(_ClientInterface):
    """
    Client for that runs in Nuke for the Nuke Adaptor
    """

    def __init__(self, server_path: str) -> None:
        super().__init__(server_path=server_path)
        self.actions.update(NukeHandler().action_dict)
        print(f"NukeClient: Nuke Version {nuke.env['NukeVersionString']}", flush=True)

        def ensure_output_dir():
            """Ensures the output directory exists before rendering"""
            output_filename = nuke.filename(nuke.thisNode())
            if not os.path.isabs(output_filename):
                output_filename = os.path.join(os.getcwd(), output_filename)
            output_dir = os.path.dirname(output_filename)
            # Filenames can contain folders, if they do and the folders do not exist, create them
            if output_dir and not os.path.isdir(output_dir):
                os.makedirs(output_dir)

        def verify_ocio_config():
            """If using an OCIO config, update the internal search paths if necessary"""
            if nuke_ocio.is_OCIO_enabled():
                self._map_ocio_config()

        nuke.addBeforeRender(verify_ocio_config)
        nuke.addBeforeRender(ensure_output_dir)
        nuke.addFilenameFilter(self.map_path)

    def close(self, args: Optional[dict] = None) -> None:
        nuke.scriptClose()
        nuke.scriptExit()

    def graceful_shutdown(self, signum: int, frame: FrameType | None):
        nuke.scriptClose()
        nuke.scriptExit()

    @lru_cache(maxsize=None)
    def map_path(self, path: str) -> str:
        """
        Override of the base map_path implementation to return the mapped path without back slashes.
        We must do this because Write nodes in nuke will error if paths contain back slashes.
        """
        rules = self.path_mapping_rules()

        rule = self._which_rule_applies(path, rules)
        # on finding rule match, if the DESTINATION PATH is a parent of the given PATH return original PATH
        # this prevents the situation where path <a>/<b> is attempting to map to itself i.e. map to <a>/<a>/<b>

        if (
            rule
            and PurePath(path).is_absolute() == PurePath(rule.destination_path).is_absolute()
            and PurePath(os.path.commonpath((path, rule.destination_path)))
            == PurePath(rule.destination_path)
        ):
            return Path(path).as_posix()

        result = super().map_path(path)
        return Path(result).as_posix()

    def _which_rule_applies(
        self, path: str, rules: List[PathMappingRule]
    ) -> PathMappingRule | None:
        """
        What rule applies to a given path?
        Takes a path and a list of rules.
        returns first rule that applies to the path. If no rules maps return None
        """
        for rule in rules:
            if (
                rule
                and PurePath(path).is_absolute() == PurePath(rule.source_path).is_absolute()
                and PurePath(os.path.commonpath((path, rule.source_path)))
                == PurePath(rule.source_path)
            ):
                return rule
        return None

    def _map_ocio_config(self):
        """If the OCIO config contains absolute search paths, apply path mapping rules and create a new config"""
        ocio_config_path = nuke_ocio.get_ocio_config_path()
        ocio_config = nuke_ocio.create_config_from_file(ocio_config_path)
        if nuke_ocio.config_has_absolute_search_paths(ocio_config):
            # make all search paths absolute since the new config will be saved in the nuke temp dir
            updated_search_paths = [
                self.map_path(search_path)
                for search_path in nuke_ocio.get_config_absolute_search_paths(ocio_config)
            ]

            nuke_ocio.update_config_search_paths(
                ocio_config=ocio_config, search_paths=updated_search_paths
            )

            # create a new version of the config with updated search paths
            updated_ocio_config_path = os.path.join(
                os.environ["NUKE_TEMP_DIR"],
                os.path.basename(ocio_config_path),
            )

            nuke.tprint("Writing updated OCIO config to {}".format(updated_ocio_config_path))

            ocio_config.serialize(updated_ocio_config_path)

            nuke_ocio.set_custom_config_path(updated_ocio_config_path)


def main():
    server_path = os.environ.get("NUKE_ADAPTOR_SERVER_PATH")
    if not server_path:
        raise OSError(
            "NukeClient cannot connect to the Adaptor because the environment variable "
            "NUKE_ADAPTOR_SERVER_PATH does not exist"
        )

    if not os.path.exists(server_path):
        raise OSError(
            "NukeClient cannot connect to the Adaptor because the socket at the path defined by "
            "the environment variable NUKE_ADAPTOR_SERVER_PATH does not exist. Got: "
            f"{os.environ['NUKE_ADAPTOR_SERVER_PATH']}"
        )

    client = NukeClient(server_path)
    client.poll()


if __name__ == "__main__":  # pragma: no cover
    main()
