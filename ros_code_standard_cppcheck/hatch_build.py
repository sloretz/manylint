import multiprocessing
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import tarfile

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


CPPCHECK_VERSION = "2.14.0"
CPPCHECK_URL = f"https://github.com/danmar/cppcheck/archive/refs/tags/{CPPCHECK_VERSION}.tar.gz"


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        build_data["pure_python"] = False
        build_data["infer_tag"] = True

        root = Path(self.root)
        bin_dir = root / "src" / "ros_code_standard_cppcheck" / "bin"
        cfg_dir = bin_dir / "cfg"
        cppcheck_bin = bin_dir / "cppcheck"
        std_cfg = cfg_dir / "std.cfg"

        if cppcheck_bin.exists() and std_cfg.exists() and self._is_static(cppcheck_bin):
            return

        build_root = Path("/tmp/build_cppcheck")
        build_root.mkdir(parents=True, exist_ok=True)
        tarball = build_root / f"cppcheck-{CPPCHECK_VERSION}.tar.gz"
        src_dir = build_root / f"cppcheck-{CPPCHECK_VERSION}"

        if not src_dir.exists():
            if not tarball.exists():
                urllib.request.urlretrieve(CPPCHECK_URL, tarball)
            with tarfile.open(tarball, "r:gz") as tar:
                tar.extractall(path=build_root)

        built_bin = src_dir / "cppcheck"
        if not (built_bin.exists() and self._is_static(built_bin)):
            jobs = multiprocessing.cpu_count()
            subprocess.check_call(
                [
                    "make",
                    f"-j{jobs}",
                    "MATCHCOMPILER=yes",
                    f"PYTHON_INTERPRETER={sys.executable}",
                    "CPPCHK_GLIBCXX_DEBUG=",
                    "CXXFLAGS=-O2 -DNDEBUG -Wall -Wno-sign-compare -Wno-multichar",
                    "LDFLAGS=-static",
                    "RDYNAMIC=",
                    "cppcheck",
                ],
                cwd=src_dir,
            )
            subprocess.run(["strip", "-s", str(built_bin)], check=False)

        bin_dir.mkdir(parents=True, exist_ok=True)
        cfg_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(built_bin, cppcheck_bin)
        os.chmod(cppcheck_bin, 0o755)

        for cfg_file in (src_dir / "cfg").glob("*.cfg"):
            shutil.copy2(cfg_file, cfg_dir / cfg_file.name)

        if not self._is_static(cppcheck_bin):
            raise RuntimeError(f"Expected static binary at {cppcheck_bin}")

    @staticmethod
    def _is_static(binary: Path) -> bool:
        res = subprocess.run(
            ["ldd", str(binary)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        return "not a dynamic executable" in res.stdout or "statically linked" in res.stdout
