# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
import numpy as np
from PIL import Image
from pathlib import Path
import cv2
import os


def verify_image_sequence_rgb_matches(
    expected_dir: str,
    output_dir: str,
    base_name: str,
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
        base_name: Base name of the image files to verify
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
        filename = f"{base_name}.{frame_str}.png"

        # Open images
        reference_img = Image.open(os.path.join(expected_dir, filename))
        output_img = Image.open(os.path.join(output_dir, filename))

        # Convert to numpy arrays
        ref_img_pixels = np.asarray(reference_img)
        out_img_pixels = np.asarray(output_img)

        ref_img_pixels = ref_img_pixels[..., :3]
        out_img_pixels = out_img_pixels[..., :3]

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


def verify_video_sequence_matches(
    expected_video: str,
    output_video: str,
    frame_interval: int = 1,
    rgb_diff_tolerance: float = 0.1,
):
    """
    Compare two video sequences by extracting frames and comparing their RGB values.
    Verifies that both videos have matching resolution, duration, and frame count,
    while also checking that the content matches between corresponding frames.

    Args:
        expected_video: Path to the expected reference video
        output_video: Path to the output video to compare
        frame_interval: Sample every nth frame (default: 1, meaning check every frame)
        rgb_diff_tolerance: Maximum allowed RGB difference (default: 0.1)
    """
    # Open both videos
    ref_cap = cv2.VideoCapture(expected_video)
    out_cap = cv2.VideoCapture(output_video)

    if not ref_cap.isOpened() or not out_cap.isOpened():
        raise ValueError("Failed to open one or both video files")

    try:
        # Compare video metadata
        ref_frame_count = int(ref_cap.get(cv2.CAP_PROP_FRAME_COUNT))
        out_frame_count = int(out_cap.get(cv2.CAP_PROP_FRAME_COUNT))
        assert ref_frame_count == out_frame_count, (
            f"Frame count mismatch: expected {ref_frame_count}, " f"got {out_frame_count}"
        )

        ref_width = int(ref_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        ref_height = int(ref_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        out_width = int(out_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        out_height = int(out_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        assert (ref_width, ref_height) == (out_width, out_height), (
            f"Resolution mismatch: expected {ref_width}x{ref_height}, "
            f"got {out_width}x{out_height}"
        )

        # Initialize RGB accumulators
        total_ref_rgb = np.zeros(3)  # [R, G, B]
        total_out_rgb = np.zeros(3)  # [R, G, B]
        total_pixels = 0
        frames_processed = 0

        # Process frames at specified intervals
        frame_idx = 0
        while True:
            ref_ret, ref_frame = ref_cap.read()
            out_ret, out_frame = out_cap.read()

            if not ref_ret or not out_ret:
                break

            if frame_idx % frame_interval == 0:
                # Convert BGR to RGB (cv2 reads in BGR format)
                ref_frame_rgb = cv2.cvtColor(ref_frame, cv2.COLOR_BGR2RGB)
                out_frame_rgb = cv2.cvtColor(out_frame, cv2.COLOR_BGR2RGB)

                # Accumulate RGB values
                total_ref_rgb += ref_frame_rgb.sum(axis=(0, 1))
                total_out_rgb += out_frame_rgb.sum(axis=(0, 1))
                total_pixels += ref_height * ref_width
                frames_processed += 1

            frame_idx += 1

        if frames_processed == 0:
            raise ValueError("No frames were processed")

        # Compute average RGB across all processed frames
        avg_ref_rgb = total_ref_rgb / total_pixels
        avg_out_rgb = total_out_rgb / total_pixels

        # Compare RGB difference
        diff = avg_ref_rgb - avg_out_rgb
        video_err = np.sum(diff**2)

        print(f"Average RGB difference across {frames_processed} frames: {video_err}")
        assert (
            video_err <= rgb_diff_tolerance
        ), f"RGB difference {video_err} exceeds tolerance {rgb_diff_tolerance}"

    finally:
        # Clean up
        ref_cap.release()
        out_cap.release()


def count_files(directory, extension=".png"):
    return len(list(Path(directory).glob(f"*{extension}")))
