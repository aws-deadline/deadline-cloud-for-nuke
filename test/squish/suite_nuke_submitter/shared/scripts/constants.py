# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
import os

DEADLINE_NUKE_PATH = os.environ.get("DEADLINE_NUKE_PATH", "")

TEST_SAMPLES_BASE = os.path.join(
    DEADLINE_NUKE_PATH, "test", "squish", "nuke-assets", "nuke_test_samples"
)


class TestConstants:
    # Test sample directories
    DEFAULT_TEST_SAMPLES_DIR = os.path.join(
        TEST_SAMPLES_BASE, "nuke_submitter_v02_nuke_default_test_samples"
    )
    MODIFIED_TEST_SAMPLES_DIR = os.path.join(
        TEST_SAMPLES_BASE, "nuke_submitter_v02_nuke_modified_test_samples"
    )
    ACES_STOCK_TEST_SAMPLES_DIR = os.path.join(
        TEST_SAMPLES_BASE, "nuke_submitter_v02_nuke_aces_stock_test_samples"
    )
    ACES_CUSTOM_TEST_SAMPLES_DIR = os.path.join(
        TEST_SAMPLES_BASE, "nuke_submitter_v02_nuke_aces_custom_samples"
    )
    INTRO_COMPOSITION_TEST_SAMPLES_DIR = os.path.join(
        TEST_SAMPLES_BASE, "intro_to_compositing_test_samples"
    )

    @staticmethod
    def get_expected_img_dir(test_samples_dir):
        return os.path.join(test_samples_dir, "images", "expected")

    @staticmethod
    def get_output_img_dir(test_samples_dir):
        return os.path.join(test_samples_dir, "images", "output")

    @staticmethod
    def get_expected_mov_dir(test_samples_dir):
        return os.path.join(test_samples_dir, "movies", "expected")

    @staticmethod
    def get_output_mov_dir(test_samples_dir):
        return os.path.join(test_samples_dir, "movies", "output")

    @staticmethod
    def get_script_dir(test_samples_dir):
        return os.path.join(test_samples_dir, "scripts")

    FRAME_RANGE = (101, 120)
    RGB_TOLERANCE = 0.1
