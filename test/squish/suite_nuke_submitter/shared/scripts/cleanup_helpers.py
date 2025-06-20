# -*- coding: utf-8 -*-
import glob
from pathlib import Path

def cleanup_output_images(
    output_dir: str,
    base_name: str = "nukeTest_output_OCIO_v01",
    start_frame: int = 101,
    end_frame: int = 152
) -> tuple[bool, str]:
    """
    Delete all output images in the specified directory that match the frame sequence pattern.
    
    Args:
        output_dir: Directory containing output images to delete
        base_name: Base name of the image files
        start_frame: First frame number
        end_frame: Last frame number
        
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
            
        # Delete each frame
        for frame in range(start_frame, end_frame + 1):
            frame_str = f"{frame:04d}"  # e.g. 0101
            filename = f"{base_name}.{frame_str}.png"
            file_path = output_path / filename
            
            if file_path.exists():
                file_path.unlink()
                deleted_count += 1
                
        # Also clean up any other PNG files in case frame range changed
        pattern = str(output_path / f"{base_name}.[0-9][0-9][0-9][0-9].png")
        for file_path in glob.glob(pattern):
            Path(file_path).unlink()
            deleted_count += 1
            
        return True, f"Successfully deleted {deleted_count} output images"
        
    except Exception as e:
        return False, f"Error cleaning up output images: {str(e)}"
