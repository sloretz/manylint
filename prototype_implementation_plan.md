# `manylint` Prototype Implementation Plan (For LLM Agents)

You are building the `manylint` prototype inside `/workspaces/ros2/manylint`.
Follow this plan step-by-step. Use **active voice**, **simple Python**, and the **`hatchling` build backend** (`pyproject.toml`) for every package.

---

## 1. Repository Layout

Create all packages as top-level directories inside `/workspaces/ros2/manylint/`.
* The top-level CLI orchestrator package is **`manylint/`**.
* Each individual linter + ROS 2 configuration package is prefixed with **`ros_code_standard_`**:

```text
/workspaces/ros2/manylint/
├── .pre-commit-hooks.yaml                   # Exposes hooks to pre-commit
├── manylint/                                # Main package: CLI, pre-commit runner, JUnit aggregator
│   ├── pyproject.toml
│   └── src/manylint/
│       ├── __init__.py
│       ├── cli.py                           # `manylint [options] [paths ...]` entry point
│       ├── discovery.py                     # Finds git repos & ROS packages (skips AMENT_IGNORE/COLCON_IGNORE)
│       ├── junit.py                         # Aggregates per-linter XUnit files into --output=junit
│       └── data/
│           └── default_pre_commit_config.yaml
├── ros_code_standard_uncrustify/            # Static C++ uncrustify binary + ament_code_style.cfg
├── ros_code_standard_cppcheck/              # Static C++ cppcheck binary + runner
├── ros_code_standard_xmllint/               # Static C xmllint binary (or lxml) + ROS package_format2/3.xsd
├── ros_code_standard_cpplint/               # Vendored cpplint.py + ROS 2 header guard/filter rules
├── ros_code_standard_lint_cmake/            # Vendored cmakelint.py + ROS 2 CMake rules
├── ros_code_standard_copyright/             # Vendored ament_copyright + license templates
├── ros_code_standard_flake8/                # Pinned flake8 + 7 plugins + ament_flake8.ini
└── ros_code_standard_pep257/                # Pinned pydocstyle + ament_pep257 conventions
```

---

## 2. Multi-Agent Workflow Overview

Execute the build in **three phases**:

1. **Phase 1 (Main Agent — Interface & Scaffold)**:
   * Define the CLI and Python interface contract that every `ros_code_standard_<linter>` package must follow.
   * Create the `/workspaces/ros2/manylint/manylint/` package skeleton.
2. **Phase 2 (Parallel Subagents — Build Each `ros_code_standard_<linter>` Package)**:
   * Spawn one subagent per `ros_code_standard_<linter>` directory.
   * Because each subagent works exclusively inside `/workspaces/ros2/manylint/ros_code_standard_<linter>/`, subagents never edit the same files.
   * Each subagent compiles its static binary (for C/C++ tools), wraps it with `hatchling`, and tests its CLI (`ros-code-standard-<linter>`) independently.
3. **Phase 3 (Main Agent — Final Integration & Verification)**:
   * Install all `ros_code_standard_*` packages into a shared test environment.
   * Implement the `manylint` CLI orchestrator (`manylint/src/manylint/cli.py`), `.pre-commit-hooks.yaml`, and `default_pre_commit_config.yaml`.
   * Run `manylint` end-to-end on real ROS 2 packages in `/workspaces/ros2/src/`.

---

## 3. Phase 1: Main Agent — Define Interfaces Between Packages

Every `ros_code_standard_<linter>` package MUST implement the exact same CLI and Python interface so `manylint` and `pre-commit` can invoke all of them uniformly.

### A. Required Python API (`ros_code_standard_<linter>/__init__.py`)
Every package must expose:
```python
from pathlib import Path

def run(argv: list[str] | None = None) -> int:
    """Run the linter with CLI arguments. Return 0 if clean, 1 if violations or file edits occurred."""

def get_executable() -> Path | None:
    """Return path to the bundled static binary (for C/C++ tools), or None for pure-Python linters."""
```

### B. Required CLI Contract (`ros-code-standard-<linter>`)
Every package must declare a console script in `pyproject.toml`:
```toml
[project.scripts]
ros-code-standard-<linter> = "ros_code_standard_<linter>.cli:main"
```
The CLI script must:
1. Accept positional `paths` (`nargs="*"`, defaulting to `["."]`).
2. Accept `--xunit-file <path>` to write JUnit/XUnit XML results.
3. Also check the environment variable `MANYLINT_JUNIT_DIR`: if set and `--xunit-file` is not passed, automatically write an XUnit report to `$MANYLINT_JUNIT_DIR/<linter>.xunit.xml`.
4. **Auto-fix behavior**:
   * If the linter supports fixing (`ros_code_standard_uncrustify`, `ros_code_standard_xmllint`), **always format files in-place** (`--reformat` / `--format`) and return exit code `1` if any file was modified (matching `pre-commit` and `ament_uncrustify --reformat`).
   * If the linter is check-only (`ros_code_standard_cppcheck`, `ros_code_standard_cpplint`, `ros_code_standard_flake8`, `ros_code_standard_pep257`, `ros_code_standard_lint_cmake`, `ros_code_standard_copyright`), check the files and return exit code `1` if any violation is found.

### C. Required `pyproject.toml` Template (`hatchling`)
Use `hatchling` for every package:

* **For Pure-Python Packages (`ros_code_standard_cpplint`, `ros_code_standard_lint_cmake`, `ros_code_standard_copyright`, `ros_code_standard_flake8`, `ros_code_standard_pep257`)**:
  ```toml
  [build-system]
  requires = ["hatchling"]
  build-backend = "hatchling.build"

  [project]
  name = "ros-code-standard-<linter>"
  version = "0.1.0"
  requires-python = ">=3.10"
  dependencies = []

  [project.scripts]
  ros-code-standard-<linter> = "ros_code_standard_<linter>.cli:main"

  [tool.hatch.build.targets.wheel]
  packages = ["src/ros_code_standard_<linter>"]
  ```

* **For Static Binary C/C++ Packages (`ros_code_standard_uncrustify`, `ros_code_standard_cppcheck`, `ros_code_standard_xmllint`)**:
  Use a `hatch_build.py` custom build hook with `hatchling` to compile the static binary (`-static`) during wheel build and bundle it inside `src/ros_code_standard_<linter>/bin/`:
  ```toml
  [build-system]
  requires = ["hatchling"]
  build-backend = "hatchling.build"

  [project]
  name = "ros-code-standard-<linter>"
  version = "0.1.0"
  requires-python = ">=3.10"

  [project.scripts]
  ros-code-standard-<linter> = "ros_code_standard_<linter>.cli:main"

  [tool.hatch.build.targets.wheel]
  packages = ["src/ros_code_standard_<linter>"]

  [tool.hatch.build.targets.wheel.hooks.custom]
  path = "hatch_build.py"
  ```
  In `hatch_build.py`:
  ```python
  from hatchling.builders.hooks.plugin.interface import BuildHookInterface
  import subprocess
  from pathlib import Path

  class CustomBuildHook(BuildHookInterface):
      def initialize(self, version, build_data):
          build_data["pure_python"] = False
          build_data["infer_tag"] = True
          # Compile static C/C++ binary with -static and place in src/ros_code_standard_<linter>/bin/<tool>
          # Verify with `ldd` that the binary has zero dynamic library dependencies.
  ```

---

## 4. Phase 2: Subagent Tasks for Each `ros_code_standard_<linter>` Package

Launch subagents in parallel. Give each subagent its specific assignment below:

### Subagent 1: `ros_code_standard_uncrustify/`
* **Directory**: `/workspaces/ros2/manylint/ros_code_standard_uncrustify/`
* **Source Reference**: `/workspaces/ros2/src/ament/ament_lint/ament_uncrustify/`
* **Steps**:
  1. In `hatch_build.py`, fetch or build `uncrustify` (`0.78.1`) from C++ source with `CMAKE_EXE_LINKER_FLAGS="-static"` (or `g++ -static -O2`), placing the static binary at `src/ros_code_standard_uncrustify/bin/uncrustify`. Verify `ldd` prints `not a dynamic executable`.
  2. Copy `ament_code_style_0_78.cfg` from `/workspaces/ros2/src/ament/ament_lint/ament_uncrustify/ament_uncrustify/configuration/ament_code_style_0_78.cfg` into `src/ros_code_standard_uncrustify/configuration/`.
  3. Adapt `ament_uncrustify/main.py` into `src/ros_code_standard_uncrustify/cli.py` so that it always uses the bundled `bin/uncrustify` executable, defaults to `--reformat` (so `pre-commit` auto-fixes files in-place and returns `1` when divergences are fixed), and writes `--xunit-file` when `$MANYLINT_JUNIT_DIR` is set.
  4. Test by building the wheel (`pip install -e .` or `pip wheel .`) and running `ros-code-standard-uncrustify` on a sample `.cpp` file.

### Subagent 2: `ros_code_standard_cppcheck/`
* **Directory**: `/workspaces/ros2/manylint/ros_code_standard_cppcheck/`
* **Source Reference**: `/workspaces/ros2/src/ament/ament_lint/ament_cppcheck/`
* **Steps**:
  1. In `hatch_build.py`, compile `cppcheck` from C++ source with `-static` (`g++ -static -O2` on `cli/*.cpp`, `lib/*.cpp`, `externals/simplecpp/*.cpp`, `externals/tinyxml2/*.cpp`, `externals/picojson/*.cpp`), placing the static binary at `src/ros_code_standard_cppcheck/bin/cppcheck` and `cfg/std.cfg` at `src/ros_code_standard_cppcheck/bin/cfg/std.cfg`.
  2. Adapt `ament_cppcheck/main.py` into `src/ros_code_standard_cppcheck/cli.py` so it uses the bundled `bin/cppcheck` binary and supports `$MANYLINT_JUNIT_DIR`.
  3. Test by running `ros-code-standard-cppcheck` on a sample `.cpp` file.

### Subagent 3: `ros_code_standard_xmllint/`
* **Directory**: `/workspaces/ros2/manylint/ros_code_standard_xmllint/`
* **Source Reference**: `/workspaces/ros2/src/ament/ament_lint/ament_xmllint/`
* **Steps**:
  1. Bundle `package_format2.xsd` and `package_format3.xsd` inside `src/ros_code_standard_xmllint/schemas/` so `package.xml` validation works 100% offline.
  2. Either compile `xmllint` statically from `libxml2` in `hatch_build.py` (`src/ros_code_standard_xmllint/bin/xmllint`) OR use `lxml` (`lxml.etree.XMLSchema`) in Python.
  3. Implement `src/ros_code_standard_xmllint/cli.py` to validate XML files against their declared schemas, format XML files if needed, and emit `$MANYLINT_JUNIT_DIR/xmllint.xunit.xml`.

### Subagent 4: `ros_code_standard_cpplint/`
* **Directory**: `/workspaces/ros2/manylint/ros_code_standard_cpplint/`
* **Source Reference**: `/workspaces/ros2/src/ament/ament_lint/ament_cpplint/`
* **Steps**:
  1. Copy `cpplint.py` and `main.py` from `/workspaces/ros2/src/ament/ament_lint/ament_cpplint/ament_cpplint/` into `src/ros_code_standard_cpplint/`.
  2. Add `MANYLINT_JUNIT_DIR` support in `cli.py`.
  3. Build with `hatchling` and test `ros-code-standard-cpplint`.

### Subagent 5: `ros_code_standard_lint_cmake/`
* **Directory**: `/workspaces/ros2/manylint/ros_code_standard_lint_cmake/`
* **Source Reference**: `/workspaces/ros2/src/ament/ament_lint/ament_lint_cmake/`
* **Steps**:
  1. Copy `cmakelint.py` and `main.py` from `/workspaces/ros2/src/ament/ament_lint/ament_lint_cmake/ament_lint_cmake/` into `src/ros_code_standard_lint_cmake/`.
  2. Add `MANYLINT_JUNIT_DIR` support in `cli.py`.
  3. Build with `hatchling` and test `ros-code-standard-lint-cmake`.

### Subagent 6: `ros_code_standard_copyright/`
* **Directory**: `/workspaces/ros2/manylint/ros_code_standard_copyright/`
* **Source Reference**: `/workspaces/ros2/src/ament/ament_lint/ament_copyright/`
* **Steps**:
  1. Copy the `ament_copyright` module and `data/` license templates from `/workspaces/ros2/src/ament/ament_lint/ament_copyright/ament_copyright/` into `src/ros_code_standard_copyright/`.
  2. Add `MANYLINT_JUNIT_DIR` support in `cli.py`.
  3. Build with `hatchling` and test `ros-code-standard-copyright`.

### Subagent 7: `ros_code_standard_flake8/` and `ros_code_standard_pep257/`
* **Directories**: `/workspaces/ros2/manylint/ros_code_standard_flake8/` and `/workspaces/ros2/manylint/ros_code_standard_pep257/`
* **Source References**: `/workspaces/ros2/src/ament/ament_lint/ament_flake8/` and `/workspaces/ros2/src/ament/ament_lint/ament_pep257/`
* **Steps**:
  1. Copy `ament_flake8/main.py` and `configuration/ament_flake8.ini` into `ros_code_standard_flake8/src/ros_code_standard_flake8/`, pinning `flake8` and its 7 plugins in `pyproject.toml`.
  2. Copy `ament_pep257/main.py` into `ros_code_standard_pep257/src/ros_code_standard_pep257/`, pinning `pydocstyle` in `pyproject.toml`.
  3. Add `MANYLINT_JUNIT_DIR` support to both and verify `ros-code-standard-flake8` and `ros-code-standard-pep257`.

---

## 5. Phase 3: Main Agent — Integrate Everything into `manylint/`

Once all subagents complete their `ros_code_standard_*` packages, the Main Agent integrates them into `/workspaces/ros2/manylint/manylint/`:

1. **Configure `/workspaces/ros2/manylint/manylint/pyproject.toml`**:
   * Use `hatchling` as the build backend.
   * Declare dependencies on `pre-commit` and all 8 `ros-code-standard-*` packages:
     `ros-code-standard-uncrustify`, `ros-code-standard-cppcheck`, `ros-code-standard-xmllint`, `ros-code-standard-cpplint`, `ros-code-standard-lint-cmake`, `ros-code-standard-copyright`, `ros-code-standard-flake8`, `ros-code-standard-pep257`.
   * Expose `[project.scripts]`: `manylint = "manylint.cli:main"`.

2. **Create `manylint/src/manylint/data/default_pre_commit_config.yaml` and `/workspaces/ros2/manylint/.pre-commit-hooks.yaml`**:
   * Define the 8 default hooks (`uncrustify`, `cppcheck`, `cpplint`, `flake8`, `pep257`, `lint_cmake`, `xmllint`, `copyright`) invoking `ros-code-standard-<linter>` with `language: system` (so `pre-commit` uses the already-installed `ros-code-standard-*` entry points directly with zero virtualenv download delay!).

3. **Implement `manylint/src/manylint/cli.py`**:
   * Parse CLI arguments (`paths`, `-l/--linters`, `--git-diff`, `--git-staged`, `--output {text,junit}`, `--junit-file`, `--junit-dir`, `--exclude`, `-j/--jobs`).
   * Discover all target Git repositories or ROS package directories under `paths` (skipping `AMENT_IGNORE` and `COLCON_IGNORE`).
   * For each target directory:
     * Choose `<target>/.pre-commit-config.yaml` if it exists; otherwise use `default_pre_commit_config.yaml`.
     * Set `MANYLINT_JUNIT_DIR=<temp_dir>/<target_name>` and invoke `pre-commit run` (passing `--all-files`, `--from-ref`/`--to-ref` for `--git-diff`, or staged mode for `--git-staged`, and filtering by `hook_id` if `--linters` is specified).
   * Collect all `<temp_dir>/<target_name>/*.xunit.xml` files:
     * If `--output=text`, print the human-readable results and summary.
     * If `--output=junit`, merge the XUnit files into a single `<testsuites name="manylint">` XML document (`stdout` or `--junit-file`) or copy them into `--junit-dir`.

4. **End-to-End Verification**:
   * Run `manylint /workspaces/ros2/src/ament/ament_lint/ament_lint_auto` in `--output=text` and `--output=junit` modes.
   * Verify that formatting divergences are fixed in-place and reported in JUnit XML, and that clean packages exit with `0`.

---

## 6. Multi-OS / Multi-Architecture Support & Release Process

### A. Which Packages Need Multi-Platform Wheel Builds?

Not all packages need to be built on multiple platforms:

1. **7 Pure-Python Universal Packages (`*-py3-none-any.whl`) — Built Once**:
   * `manylint`, `ros_code_standard_cpplint`, `ros_code_standard_lint_cmake`, `ros_code_standard_copyright`, `ros_code_standard_flake8`, `ros_code_standard_pep257`, and `ros_code_standard_xmllint` (when using `lxml`, which already publishes its own binary wheels on PyPI for every OS/arch).
   * These contain only Python files and static config/schema files (`.cfg`, `.ini`, `.xsd`).
   * You build them **once** on a single Linux runner (`hatch build -t wheel`), and the resulting `*-py3-none-any.whl` works on every OS (`Linux`, `macOS`, `Windows`), every CPU architecture (`amd64`, `arm64`), and every Python 3 version (`3.10+`).

2. **2 Native Binary Packages (`*-py3-none-<platform>.whl`) — Built per OS/Arch (NOT per Python version!)**:
   * `ros_code_standard_uncrustify` and `ros_code_standard_cppcheck` bundle compiled C++ executables (`bin/uncrustify` and `bin/cppcheck`).
   * Because they bundle standalone executables (and do **not** link against `libpython` or the CPython C API), `hatch_build.py` sets the wheel tag to `py3-none-<platform_tag>` (for example, `ros_code_standard_uncrustify-0.1.0-py3-none-manylinux_2_17_x86_64.whl`).
   * This means you only build **5 wheels total per binary package** (1 per OS/arch target), rather than multiplying by every Python version (`cp310`, `cp311`, `cp312`, `cp313`):
     1. `py3-none-manylinux_2_17_x86_64.whl` (`linux-amd64`)
     2. `py3-none-manylinux_2_17_aarch64.whl` (`linux-arm64`)
     3. `py3-none-macosx_11_0_arm64.whl` (`osx-arm64` Apple Silicon)
     4. `py3-none-macosx_10_9_x86_64.whl` (`osx-amd64` Intel)
     5. `py3-none-win_amd64.whl` (`windows-amd64`)

### B. How the Release Pipeline Works (`git tag vX.Y.Z`)

When you push a release tag (`vX.Y.Z`), a GitHub Actions workflow runs four stages:

1. **Stage 1 — Build Universal Pure-Python Wheels (1 runner, ~15s)**:
   * Runs `hatch build -t wheel` on `ubuntu-latest` for `manylint` and the pure-Python `ros_code_standard_*` packages, producing `*-py3-none-any.whl`.
2. **Stage 2 — Build Native Binary Wheels (5-runner OS/arch matrix, or `zig c++` cross-compile)**:
   * Runs `hatch build -t wheel` across GitHub Actions' 5 native runners (`ubuntu-24.04`, `ubuntu-24.04-arm`, `macos-14`, `macos-13`, `windows-latest`) for `ros_code_standard_uncrustify` and `ros_code_standard_cppcheck`, producing the 5 `*-py3-none-<platform>.whl` wheels.
   * *(Optimization: Because `uncrustify` and `cppcheck` rarely change, these binary wheels only need to be rebuilt when their upstream C++ version or wrapper changes.)*
3. **Stage 3 — Build Standalone Static Executables (`PyApp` across 5 OS/arch runners)**:
   * On each of the 5 OS/arch matrix runners, downloads the newly built `manylint` wheel + all pinned `ros_code_standard_*` `.whl` files for that platform and compiles `PyApp` (`PYAPP_DISTRIBUTION_EMBED=true`, `PYAPP_PROJECT_EMBED_WHEELS=true`), producing:
     * `manylint-linux-amd64`
     * `manylint-linux-arm64`
     * `manylint-osx-arm64`
     * `manylint-osx-amd64`
     * `manylint-windows-amd64.exe`
4. **Stage 4 — Publish to PyPI and GitHub Releases**:
   * Uploads all `.whl` files to **PyPI** (so `pipx install manylint`, `uvx manylint`, and `pre-commit` work immediately on all 5 platforms).
   * Uploads the 5 standalone `manylint-<os>-<arch>` static binaries, `SHA256SUMS`, and `install.sh` to **GitHub Releases** (so `curl -fsSL .../install.sh | bash` works on bare machines without Python).
