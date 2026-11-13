# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Readiness rules shared by the Qt driver and its unlicensed regression tests."""


def ready_for_configuration(submit_enabled, queue_state, farm_resolved):
    if queue_state.startswith("Error loading queue environments"):
        raise RuntimeError(queue_state)
    return submit_enabled and farm_resolved and not queue_state
