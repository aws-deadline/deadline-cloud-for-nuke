# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Trial native Mesa OpenGL in a new Nuke copy on an ephemeral GitHub runner.

Never deploy to Program Files, register drivers, run upstream deployment scripts,
or modify the original installation. The release archive and individual x64
libraries are pinned to the published mesa-dist-win 26.2.6 MinGW build.
"""

import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request

ARCHIVE_URL = (
    "https://github.com/pal1000/mesa-dist-win/releases/download/26.2.6/"
    "mesa3d-26.2.6-release-mingw.7z"
)
ARCHIVE_SHA256 = "da0f71d9181b672c1918f3c342f11118c687f6059a46b16502845160733cc388"
DLL_HASHES = {
    "opengl32.dll": "281cf35807658dad1b9ec42f621b3b710a7d02da2057a6f8db3e5d0df333d788",
    "libgallium_wgl.dll": "240a95c244906d19ada0b78fa949589e14417bcea2bfa8034be0320da323530c",
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def original_hashes(source, executable):
    names = {executable.name, "python.exe", *DLL_HASHES}
    return {
        name: sha256(source / name) if (source / name).is_file() else None for name in sorted(names)
    }


def prepare(root, executable, github_env):
    source = executable.parent
    manifest = {
        "archive_url": ARCHIVE_URL,
        "archive_sha256": ARCHIVE_SHA256,
        "dll_sha256": DLL_HASHES,
        "original_directory": str(source),
        "original_executable": str(executable),
        "original_hashes": original_hashes(source, executable),
    }
    try:
        if not executable.is_file() or not (source / "python.exe").is_file():
            raise RuntimeError("Supply the verified installed Nuke executable and bundled Python")
        if source == root or source in root.parents or root in source.parents:
            raise RuntimeError("The temporary runtime must be separate from the installed runtime")
        files = list(source.rglob("*"))
        # Windows reparse points include junctions; Path.is_junction is only
        # available in Python 3.12+, while this workflow uses Python 3.11.
        if any(getattr(path.lstat(), "st_file_attributes", 0) & 0x400 for path in files):
            raise RuntimeError("Refusing to copy an installation with filesystem links")
        total = sum(path.stat().st_size for path in files if path.is_file())
        free = shutil.disk_usage(root).free
        manifest.update(copy_bytes=total, free_bytes=free)
        if free < total + 2 * 1024**3:
            raise RuntimeError(
                f"Need {total + 2 * 1024**3} free bytes for runtime copy; have {free}"
            )
        seven_zip = shutil.which("7z") or str(Path(os.environ["ProgramFiles"]) / "7-Zip" / "7z.exe")
        if not Path(seven_zip).is_file():
            raise RuntimeError("The runner image must provide 7-Zip")
        archive = root / "mesa.7z"
        urllib.request.urlretrieve(ARCHIVE_URL, archive)
        if sha256(archive) != ARCHIVE_SHA256:
            raise RuntimeError("Mesa release archive SHA-256 mismatch")
        extracted = root / "driver"
        subprocess.run(
            [
                seven_zip,
                "x",
                str(archive),
                *(f"x64/{name}" for name in DLL_HASHES),
                f"-o{extracted}",
                "-y",
            ],
            check=True,
        )
        for name, expected in DLL_HASHES.items():
            if sha256(extracted / "x64" / name) != expected:
                raise RuntimeError(f"Mesa DLL SHA-256 mismatch: {name}")
        archive.unlink()
        runtime = root / "runtime"
        shutil.copytree(source, runtime)
        for name in DLL_HASHES:
            shutil.copy2(extracted / "x64" / name, runtime / name)
        # Upstream per-application deployment uses this Windows DLL redirection
        # marker for applications that explicitly request the system OpenGL DLL.
        # It affects only the copied executable; no registry/system changes.
        (runtime / f"{executable.name}.local").write_text("", encoding="utf-8")
        copied_executable = runtime / executable.name
        manifest["runtime_executable"] = str(copied_executable)
        if sha256(copied_executable) != manifest["original_hashes"][executable.name]:
            raise RuntimeError("Copied Nuke executable differs from the original")
        os.environ["GALLIUM_DRIVER"] = "llvmpipe"
        spec = importlib.util.spec_from_file_location(
            "software_opengl_probe",
            Path(__file__).with_name("prepare-software-opengl-windows.py"),
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # Python's DLL search restrictions otherwise hide the megadriver, even
        # though it is beside opengl32.dll in Nuke's copied application directory.
        with os.add_dll_directory(str(runtime)):
            manifest["opengl"] = module.probe(runtime / "opengl32.dll")
        manifest["original_unchanged"] = (
            original_hashes(source, executable) == manifest["original_hashes"]
        )
        if not manifest["original_unchanged"]:
            raise RuntimeError("Original runtime verification failed")
        with github_env.open("a", encoding="utf-8") as env:
            env.write(
                f"NUKE_EXECUTABLE={copied_executable}\nNUKE_PYTHON={runtime / 'python.exe'}\n"
                "GALLIUM_DRIVER=llvmpipe\nQT_OPENGL=desktop\nQT_OPENGL_DLL=\n"
                "QT_LOGGING_RULES=qt.qpa.gl=true\n"
            )
    except Exception as error:
        manifest["error"] = str(error)
        raise
    finally:
        (root / "probe.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(json.dumps(manifest, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--nuke-executable", type=Path)
    parser.add_argument("--github-env", type=Path)
    parser.add_argument("--verify-original", action="store_true")
    args = parser.parse_args()
    if (
        sys.platform != "win32"
        or ctypes.sizeof(ctypes.c_void_p) != 8
        or os.environ.get("GITHUB_ACTIONS") != "true"
    ):
        raise RuntimeError("This isolated trial requires a 64-bit Windows GitHub runner")
    root = args.directory.resolve()
    temporary = Path(os.environ["RUNNER_TEMP"]).resolve()
    if temporary not in root.parents:
        raise RuntimeError("Trial directory must be a child of RUNNER_TEMP")
    if args.verify_original:
        manifest = json.loads((root / "probe.json").read_text(encoding="utf-8"))
        executable = Path(manifest["original_executable"])
        unchanged = original_hashes(executable.parent, executable) == manifest["original_hashes"]
        manifest["original_unchanged_after_tests"] = unchanged
        (root / "probe.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        if not unchanged:
            raise RuntimeError("Original Nuke files differ after the trial")
        print("Original Nuke executable, Python, and overlay-target files are unchanged.")
        return
    if not args.nuke_executable or not args.github_env:
        parser.error("--nuke-executable and --github-env are required for preparation")
    root.mkdir(exist_ok=False, parents=True)
    prepare(root, args.nuke_executable.resolve(), args.github_env)


if __name__ == "__main__":
    main()
