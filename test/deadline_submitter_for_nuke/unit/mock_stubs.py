# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations


class MockOCIOConfig:
    """Mock class which emulates an OCIO Config"""

    __name__ = "Config"

    def __init__(self, search_paths: list[str]):
        self._search_paths = search_paths

    def getSearchPaths(self) -> list[str]:
        return self._search_paths
