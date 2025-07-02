import os

NUKE_ASSET_ROOT = os.environ.get("NUKE_ASSET_ROOT", "")

class TestConstants:
    # Test sample directories
    DEFAULT_TEST_SAMPLES_DIR = f"{NUKE_ASSET_ROOT}/nuke_test_samples/nuke_submitter_v02_nuke_default_test_samples"
    MODIFIED_TEST_SAMPLES_DIR = f"{NUKE_ASSET_ROOT}/nuke_test_samples/nuke_submitter_v02_nuke_modified_test_samples"

    @staticmethod
    def get_expected_img_dir(test_samples_dir):
        return f"{test_samples_dir}/images/expected"
    
    @staticmethod
    def get_output_img_dir(test_samples_dir):
        return f"{test_samples_dir}/images/output"
    
    @staticmethod
    def get_expected_mov_dir(test_samples_dir):
        return f"{test_samples_dir}/movies/expected"
    
    @staticmethod
    def get_output_mov_dir(test_samples_dir):
        return f"{test_samples_dir}/movies/output"

    FRAME_RANGE = (101, 120)
    RGB_TOLERANCE = 0.1
