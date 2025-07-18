# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#!/usr/bin/env python3
import os
from pathlib import Path
import argparse
import sys


def replace_env_paths_in_file(file_path: str, revert: bool = False) -> None:
    """
    Replace paths in a file, either converting to actual paths or back to env vars.

    Args:
        file_path: Path to the Nuke script file
        revert: If True, converts actual paths back to $DEADLINE_NUKE_PATH
    """
    deadline_nuke_path = os.environ.get("DEADLINE_NUKE_PATH")
    if not deadline_nuke_path:
        raise ValueError("DEADLINE_NUKE_PATH environment variable is not set")

    with open(file_path, "r") as f:
        content = f.read()

    modified_content = content
    if revert:
        # Convert actual paths back to env var
        if sys.platform == "win32":
            deadline_nuke_path = deadline_nuke_path.replace("\\", "/")
            print(deadline_nuke_path)
        if deadline_nuke_path in modified_content:
            modified_content = modified_content.replace(deadline_nuke_path, "$DEADLINE_NUKE_PATH")
    else:
        if "$DEADLINE_NUKE_PATH" in modified_content:
            if sys.platform == "win32":
                deadline_nuke_path = deadline_nuke_path.replace("\\", "/")
            modified_content = modified_content.replace("$DEADLINE_NUKE_PATH", deadline_nuke_path)

    # Only write if changes were made
    if modified_content != content:
        with open(file_path, "w") as f:
            f.write(modified_content)
        action = "Reverted" if revert else "Updated"
        print(f"{action}: {file_path}")
    else:
        print(f"No changes needed: {file_path}")


def process_files(revert: bool = False) -> None:
    """Process all .nk files, either replacing or reverting paths."""
    deadline_nuke_path = os.environ.get("DEADLINE_NUKE_PATH")
    if not deadline_nuke_path:
        print("Error: DEADLINE_NUKE_PATH environment variable is not set")
        return

    # Path to search for .nk files
    search_path = os.path.join(
        deadline_nuke_path, "test", "squish", "nuke-assets", "nuke_test_samples"
    )

    # Find all .nk files recursively
    nk_files = list(Path(search_path).rglob("*.nk"))

    if not nk_files:
        print(f"No .nk files found in {search_path}")
        return

    action = "revert" if revert else "process"
    print(f"Found {len(nk_files)} .nk files to {action}")

    # Process each file
    for file_path in nk_files:
        try:
            replace_env_paths_in_file(str(file_path), revert)
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")

    print(f"\nDone! All .nk files have been {'reverted' if revert else 'processed'}.")


def main():
    parser = argparse.ArgumentParser(
        description="Replace or revert DEADLINE_NUKE_PATH in .nk files"
    )
    parser.add_argument(
        "--revert", action="store_true", help="Revert actual paths back to $DEADLINE_NUKE_PATH"
    )
    args = parser.parse_args()

    process_files(args.revert)


if __name__ == "__main__":
    main()
