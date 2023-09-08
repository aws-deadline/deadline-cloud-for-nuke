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
        HTTPClientInterface as _HTTPClientInterface,
        PathMappingRule,
    )
    from nuke_adaptor.NukeClient.nuke_handler import NukeHandler  # type: ignore[import]
except ImportError:
    from openjd.adaptor_runtime_client import (
        HTTPClientInterface as _HTTPClientInterface,
        PathMappingRule,
    )
    from deadline.nuke_adaptor.NukeClient.nuke_handler import NukeHandler

try:
    import nuke
except ImportError:  # pragma: no cover
    raise OSError("Could not find the Nuke module. Are you running this inside of Nuke?")


class NukeClient(_HTTPClientInterface):
    """
    Client for that runs in Nuke for the Nuke Adaptor
    """

    def __init__(self, socket_path: str) -> None:
        super().__init__(socket_path=socket_path)
        self.actions.update(NukeHandler().action_dict)

        def ensure_output_dir():
            """Ensures the output directory exists before rendering"""
            output_dir = os.path.dirname(nuke.filename(nuke.thisNode()))
            # Filenames can contain folders, if they do and the folders do not exist, create them
            if output_dir and not os.path.isdir(output_dir):
                os.makedirs(output_dir)

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


def main():
    socket_path = os.environ.get("NUKE_ADAPTOR_SOCKET_PATH")
    if not socket_path:
        raise OSError(
            "NukeClient cannot connect to the Adaptor because the environment variable "
            "NUKE_ADAPTOR_SOCKET_PATH does not exist"
        )

    if not os.path.exists(socket_path):
        raise OSError(
            "NukeClient cannot connect to the Adaptor because the socket at the path defined by "
            "the environment variable NUKE_ADAPTOR_SOCKET_PATH does not exist. Got: "
            f"{os.environ['NUKE_ADAPTOR_SOCKET_PATH']}"
        )

    client = NukeClient(socket_path)
    client.poll()


if __name__ == "__main__":  # pragma: no cover
    main()
