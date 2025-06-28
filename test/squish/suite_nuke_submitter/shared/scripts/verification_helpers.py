# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
import numpy as np
from PIL import Image


def verify_image_sequence_rgb_matches(
    expected_dir: str,
    output_dir: str,
    start_frame: int = 101,
    end_frame: int = 120,
    rgb_diff_tolerance: float = 0.1,
):
    """
    Compare RGB values between expected and output image sequences.
    Uses same RGB comparison logic as verify_img_rgb_matches.

    Args:
        expected_dir: Directory containing expected images
        output_dir: Directory containing output images
        start_frame: First frame number
        end_frame: Last frame number
        rgb_diff_tolerance: Maximum allowed RGB difference
    """
    total_ref_rgb = np.zeros(3)  # [R, G, B]
    total_out_rgb = np.zeros(3)  # [R, G, B]
    total_pixels = 0

    # Process each frame
    for frame in range(start_frame, end_frame + 1):
        frame_str = f"{frame:04d}"  # e.g. 0101
        filename = f"nukeTest_output_OCIO_v01.{frame_str}.png"

        # Open images
        reference_img = Image.open(f"{expected_dir}/{filename}")
        output_img = Image.open(f"{output_dir}/{filename}")

        # Convert to numpy arrays
        ref_img_pixels = np.asarray(reference_img)
        out_img_pixels = np.asarray(output_img)

        # Verify dimensions match
        height1, width1, channel_count1 = ref_img_pixels.shape
        height2, width2, channel_count2 = out_img_pixels.shape
        assert height1 == height2 and width1 == width2 and channel_count1 == channel_count2

        # Accumulate RGB values
        total_ref_rgb += ref_img_pixels.sum(axis=(0, 1))
        total_out_rgb += out_img_pixels.sum(axis=(0, 1))
        total_pixels += height1 * width1

    # Compute average RGB across all frames
    avg_ref_rgb = total_ref_rgb / total_pixels
    avg_out_rgb = total_out_rgb / total_pixels

    # Compare RGB difference
    diff = avg_ref_rgb - avg_out_rgb
    img_err = np.sum(diff**2)

    print(f"Average RGB difference across frames {start_frame}-{end_frame}: {img_err}")
    assert (
        img_err <= rgb_diff_tolerance
    ), f"RGB difference {img_err} exceeds tolerance {rgb_diff_tolerance}"
