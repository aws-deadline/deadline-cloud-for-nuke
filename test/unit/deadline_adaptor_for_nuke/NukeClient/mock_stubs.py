# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Any, Dict


class MockKnob:
    """Mock class which emulates the Nuke Knob"""

    _value: Any
    __name__ = "Knob"

    def __init__(self, value: Any):
        self._value = value

    def value(self) -> Any:
        return self._value

    def setValue(self, value):
        self._value = value
        return True


class MockNode:
    """Mock class which emulates the Nuke Node"""

    _knobs: Dict[str, MockKnob]
    _name: str = ""
    _class: str = ""
    __name__ = "Node"

    def __init__(self, name, knobs, class_name) -> None:
        self._name = name
        self._knobs = knobs
        self._class = class_name

    def name(self) -> str:
        return self._name

    def knobs(self) -> Dict[str, MockKnob]:
        return self._knobs

    def knob(self, name) -> Any:
        return self._knobs.get(name)

    def Class(self) -> str:
        return self._class
