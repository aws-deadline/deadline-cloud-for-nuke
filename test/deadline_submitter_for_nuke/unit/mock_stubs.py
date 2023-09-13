# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import List


class MockOCIOConfig:
    """Mock class which emulates an OCIO Config"""

    __name__ = "Config"

    def __init__(self, search_paths: List[str]):
        self._search_paths = search_paths

    def getSearchPaths(self) -> List[str]:
        return self._search_paths
