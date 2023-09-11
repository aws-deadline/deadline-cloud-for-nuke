# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.


class MockOCIOConfig:
    """Mock class which emulates an OCIO Config"""

    __name__ = "Config"

    def __init__(self, search_path: str):
        self._search_path = search_path

    def getSearchPath(self) -> str:
        return self._search_path
