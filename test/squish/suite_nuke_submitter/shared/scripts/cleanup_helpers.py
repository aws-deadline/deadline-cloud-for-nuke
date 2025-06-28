# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
import glob
from pathlib import Path


def cleanup_output_images(
    output_dir: str,
    base_name: str = "nukeTest_output_OCIO_v01",
) -> tuple[bool, str]:
    """
    Delete all output images in the specified directory that match the base name.

    Args:
        output_dir: Directory containing output images to delete
        base_name: Base name of the image files to delete

    Returns:
        tuple[bool, str]: (success, message)
        - success: True if all files were deleted successfully
        - message: Description of what was deleted or any errors
    """
    try:
        deleted_count = 0
        output_path = Path(output_dir)

        # Verify output directory exists
        if not output_path.exists():
            return True, f"Output directory {output_dir} does not exist, nothing to clean"

        # Find and delete all files with the base name prefix
        pattern = str(output_path / f"{base_name}.*")
        for file_path_str in glob.glob(pattern):
            file_path = Path(file_path_str)
            file_path.unlink()
            deleted_count += 1

        return True, f"Successfully deleted {deleted_count} output images"

    except Exception as e:
        return False, f"Error cleaning up output images: {str(e)}"
