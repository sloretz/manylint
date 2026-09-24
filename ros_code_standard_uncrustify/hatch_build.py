import os
import shutil
import stat
import subprocess
import urllib.request
from pathlib import Path
from hatchling.builders.hooks.plugin.interface import BuildHookInterface

UNCRUSTIFY_VERSION = "0.78.1"
UNCRUSTIFY_URL = (
    f"https://github.com/uncrustify/uncrustify/archive/refs/tags/uncrustify-{UNCRUSTIFY_VERSION}.tar.gz"
)


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict) -> None:
        build_data["pure_python"] = False
        build_data["infer_tag"] = True

        root = Path(self.root)
        bin_dir = root / "src" / "ros_code_standard_uncrustify" / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        target_bin = bin_dir / "uncrustify"

        if target_bin.exists() and os.access(target_bin, os.X_OK):
            return

        build_root = Path("/tmp/build_uncrustify")
        build_root.mkdir(parents=True, exist_ok=True)
        tarball = build_root / f"uncrustify-{UNCRUSTIFY_VERSION}.tar.gz"
        src_dir = build_root / f"uncrustify-uncrustify-{UNCRUSTIFY_VERSION}"
        cmake_build_dir = src_dir / "build"
        built_bin = cmake_build_dir / "uncrustify"

        if not built_bin.exists():
            if not tarball.exists():
                urllib.request.urlretrieve(UNCRUSTIFY_URL, tarball)
            if not src_dir.exists():
                subprocess.run(
                    ["tar", "-xzf", str(tarball), "-C", str(build_root)],
                    check=True,
                )
            cmake_build_dir.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                [
                    "cmake",
                    "-S",
                    str(src_dir),
                    "-B",
                    str(cmake_build_dir),
                    "-DCMAKE_BUILD_TYPE=Release",
                    "-DCMAKE_EXE_LINKER_FLAGS=-static",
                ],
                check=True,
            )
            subprocess.run(
                [
                    "cmake",
                    "--build",
                    str(cmake_build_dir),
                    "-j",
                    str(os.cpu_count() or 2),
                ],
                check=True,
            )

        shutil.copy2(built_bin, target_bin)
        target_bin.chmod(target_bin.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
