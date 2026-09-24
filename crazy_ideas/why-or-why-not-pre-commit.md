# `manylint` vs. `pre-commit`: Strengths, Weaknesses, and Steel-Manning `pre-commit`

A natural question when designing `manylint` is: **Why not use [`pre-commit`](https://pre-commit.com/) (or its single-binary Rust drop-in replacement, [`prek`](https://github.com/j178/prek))?**

Below is an analysis of:
1. Where `pre-commit` shines out of the box and where it initially struggles in ROS 2.
2. **Steel-manning `pre-commit`**: How we can solve *every single one* of `pre-commit`'s limitations (including making `uncrustify`, `cppcheck`, and `xmllint` 100% hermetic via PyPI binary wheels) and how that compares to building a custom Bazel static binary.

---

## 1. Initial Comparison: Out-of-the-Box `pre-commit` vs. `manylint`

### Strengths of `pre-commit` Today
1. **Already Exists & Zero Custom Build Maintenance**: Battle-tested across tens of thousands of repositories (including MoveIt 2, Nav2, and `ros2_control`).
2. **Hermetic for Tools with PyPI Binary Wheels**: Tools like `clang-format` (`clang-format` wheel on PyPI), `ruff`, `flake8`, and `cmake-format` are automatically installed into isolated, version-pinned virtual environments in `~/.cache/pre-commit/`.
3. **Rich Ecosystem of Non-ROS Hygiene Hooks**: `codespell`, `check-yaml`, `check-merge-conflict`, `check-added-large-files`, `shellcheck`, and `pre-commit.ci`.

### Initial Weaknesses of Out-of-the-Box `pre-commit` in ROS 2
1. **`uncrustify`, `cppcheck`, and `xmllint` Are Not Hermetic Today**: Because they don't publish official binary wheels on PyPI, ROS 2 repos using `pre-commit` today rely on `language: system` (`/usr/bin/uncrustify` from `apt`), reintroducing OS version drift.
2. **Config Duplication Across 100+ Git Repos**: A ROS 2 workspace (`src/`) has 100+ Git repositories; copying `.pre-commit-config.yaml`, `ament_code_style.cfg`, and `.flake8` into every repo creates massive duplication.
3. **Multi-Package Git Repos & `package.xml` Awareness**: A single Git repo (like `ament_lint` or `rclcpp`) contains multiple ROS packages, whereas `.pre-commit-config.yaml` sits at the Git repo root.
4. **Multi-Repo `src/` Workspaces**: Running `pre-commit run --all-files` directly on `/workspaces/ros2/src` fails (`not a git repository`).
5. **`check` vs. `fix` Mode & JUnit XML Output**: Hooks in `.pre-commit-config.yaml` have a single static `args:` list, and `pre-commit` only emits text output (not JUnit XML).

---

## 2. Steel-Manning `pre-commit`: Solving Every Limitation

What if, instead of building a monolithic static binary from scratch in Bazel, we invested a fraction of that effort into making the ROS 2 linter ecosystem first-class in `pre-commit`? Every single weakness above has a clean, practical engineering solution.

### A. How to Make `uncrustify`, `cppcheck`, and `xmllint` 100% Hermetic in `pre-commit`

How does `clang-format` work hermetically in `pre-commit` without requiring LLVM or a C++ compiler on the user's machine?
The `clang-format` PyPI package uses **`scikit-build-core` + `cibuildwheel`** in GitHub Actions to compile the C++ binary once per release and bundle the static executable inside platform-tagged Python wheels (`manylinux_2_17_x86_64`, `manylinux_2_17_aarch64`, `macosx_11_0_arm64`, `macosx_10_9_x86_64`, `win_amd64`). When `pip` installs the wheel into a `pre-commit` virtualenv, the binary is placed directly into `<venv>/bin/`.

We can apply this exact pattern to all three C/C++ linters:

1. **`xmllint` $\rightarrow$ Use `lxml` (Already a Hermetic Binary Wheel on PyPI!)**:
   * Why does `ament_xmllint` shell out to `/usr/bin/xmllint` (`libxml2-utils`)? Only to validate `.xml` files against XSD, RelaxNG, and Schematron schemas.
   * The Python **`lxml`** package on PyPI **already ships prebuilt binary wheels with `libxml2` and `libxslt` statically compiled inside** for Linux (`x86_64`, `aarch64`), macOS (`arm64`, `x86_64`), and Windows (`amd64`)!
   * By updating `ament_xmllint` to validate schemas in-process using `lxml.etree.XMLSchema` (and bundling `package_format2.xsd` and `package_format3.xsd` inside the package data), `ament_xmllint` becomes a **100% hermetic, zero-system-dependency Python package** immediately—without even needing a custom C binary wheel!
2. **`uncrustify` $\rightarrow$ Publish `uncrustify-wheel` (or `ament-uncrustify`) on PyPI via `cibuildwheel`**:
   * `uncrustify` is pure C++17 with zero external library dependencies.
   * A 40-line `pyproject.toml` using `scikit-build-core` + `cibuildwheel` compiles `uncrustify 0.78.1` into prebuilt wheels for all 5 platforms (`linux-amd64`, `linux-arm64`, `osx-arm64`, `osx-amd64`, `windows-amd64`).
   * Bundling `ament_code_style_0_78.cfg` inside `ament-uncrustify` on PyPI means `pip install ament-uncrustify` gives you the exact pinned `uncrustify` binary AND ROS 2 config file everywhere.
3. **`cppcheck` $\rightarrow$ Publish `cppcheck-wheel` (or `ament-cppcheck`) on PyPI via `cibuildwheel`**:
   * `cppcheck` also vendors all of its dependencies (`simplecpp`, `tinyxml2`, `picojson`) in its source tree and compiles cleanly with CMake + `scikit-build-core` into a standalone binary wheel.

**Result**: Once `ament-uncrustify`, `ament-cppcheck`, `ament-xmllint` (via `lxml`), `ament-flake8`, `ament-pep257`, `ament-cpplint`, `ament-lint-cmake`, and `ament-copyright` are published on PyPI as prebuilt wheels, **`pre-commit` (`language: python`) is 100% hermetic across Linux, macOS, and Windows with zero `apt` or system dependencies!**

---

### B. Solving Config Duplication Across 100+ Git Repositories

Instead of copying `ament_code_style.cfg`, `.flake8`, and a 60-line `.pre-commit-config.yaml` into 100+ ROS 2 repositories:

1. **Default Configs Live Inside the `ament_*` Wheels**:
   * Just as `ament_lint` already stores `ament_code_style_0_78.cfg` and `ament_flake8.ini` inside its Python package data, the `pre-commit` hooks use those built-in defaults automatically unless overridden.
2. **Provide a Single Unified Hook (`id: ament-lint`) in `ament/ament_lint`**:
   * Instead of listing 8 separate hooks in every repo's `.pre-commit-config.yaml`, `ament/ament_lint` can expose a single meta-hook in `.pre-commit-hooks.yaml` whose `additional_dependencies` pull in all 8 `ament-*` wheels:
     ```yaml
     # The entire .pre-commit-config.yaml needed in any ROS 2 repository:
     repos:
       - repo: https://github.com/ament/ament_lint
         rev: 0.21.2
         hooks:
           - id: ament-lint
     ```
3. **Zero Config Files Required in Target Repos via `pre-commit -c`**:
   * `pre-commit` supports `--config <path>` (`pre-commit run --all-files -c /path/to/ros2_default_pre_commit.yaml`).
   * ROS 2 CI (or a developer running a wrapper script) can run `pre-commit` against *any* ROS 2 repository—even one without a `.pre-commit-config.yaml` file—using a single central config file!

---

### C. Solving Per-Package Customization (`<export><manylint>`) in Multi-Package Repos

Why did `pre-commit` seem limited to Git-repository-level configuration? Only if the hooks themselves ignore `package.xml`!
* When `pre-commit` runs, it passes the list of staged/modified files (`rclcpp/src/node.cpp`, `rclcpp_action/src/client.cpp`) to the hook executable.
* For each file, the `ament-lint` hook can walk up parent directories to locate the nearest `package.xml`, parse `<export><manylint>` (or `<test_depend>`), and apply that specific ROS package's linter exclusions, `<config>`, and `<args>`!
* This gives `pre-commit` **full per-package `<export><manylint>` granularity** inside multi-package Git repositories.

---

### D. Solving Multi-Repo `src/` Workspaces (`vcstool`)

How do you run `pre-commit` across all 100+ Git repositories in `/workspaces/ros2/src`?
* `vcstool` (already standard in ROS 2) has built-in parallel command execution across all Git repositories in `src/`:
  ```bash
  vcs custom src/ --git --args run pre-commit run --all-files
  ```
* Because `pre-commit` stores hook virtual environments in a global content-addressed cache (`~/.cache/pre-commit/`), **all 100+ repositories share the exact same single virtual environment on disk** (zero duplicated installation time or disk space).

---

### E. Solving `check` vs. `fix`, JUnit XML, and Host Python Dependencies

1. **`check` vs. `fix` in `pre-commit`**:
   * By default in `pre-commit`, formatters (`uncrustify --reformat`) modify unformatted files in-place AND return exit code `1` (`files were modified by this hook`).
   * **On a developer's laptop**: Running `pre-commit run --all-files` (or `git commit`) automatically fixes the files!
   * **In CI**: Running `pre-commit run --all-files` automatically fails the build (exit code `1`) if any file needed formatting and prints the exact `git diff` of what needs to be fixed!
   * Furthermore, if a strictly read-only check or JUnit XML output is needed in CI, `ament-lint` can check an environment variable (`AMENT_LINT_CHECK_ONLY=1` or `AMENT_LINT_JUNIT_DIR=build/test_results pre-commit run --all-files`).
2. **Eliminating the Host Python Dependency with [`prek`](https://github.com/j178/prek)**:
   * [`prek`](https://github.com/j178/prek) is a fast, single-file static Rust binary that implements the `pre-commit` CLI and `.pre-commit-config.yaml` spec, using embedded `uv` logic to download standalone Python interpreters and wheels in milliseconds without needing Python or `pip` installed on the host OS.

---

## 3. Updated Architecture Comparison: Custom Bazel Binary vs. Steel-Manned `pre-commit` / PyPI Wheels

| Dimension | Option A: Custom Bazel Static Binary (`manylint`) | Option B: Steel-Manned `pre-commit` (`prek`) + Hermetic PyPI Wheels |
| :--- | :--- | :--- |
| **How C/C++ tools (`uncrustify`, `cppcheck`, `libxml2`) are packaged** | Bazel `http_archive` + static `cc_library` linked into one C++/Rust binary | `cibuildwheel` + `scikit-build-core` PyPI binary wheels (`lxml` for `xmllint`) |
| **Build & Maintenance Complexity** | **High**: Custom Bazel `BUILD` files for `uncrustify`, `cppcheck`, `libxml2`, and embedded `libpython` across 5 OS/arch targets | **Low**: Standard ~40-line `cibuildwheel` GitHub Action for `uncrustify` & `cppcheck`; pure Python wheels for everything else |
| **Reusability Outside `manylint`** | Locked inside the monolithic `manylint` binary | **High**: Anyone can `pip install ament-uncrustify ament-cppcheck` or use them in `pre-commit`, `tox`, `nox`, or `uvx` |
| **Single-Binary UX (`manylint check src/`)** | Native (`manylint` is the binary) | A tiny 200-line Python CLI entry point (`manylint`) in the same wheel can walk `src/` directly (`uvx manylint check src/` or bundled via PyInstaller/PyOxidizer) |
| **Compatibility with `.pre-commit-config.yaml` Ecosystem** | Requires a wrapper hook | **Native**: Works seamlessly alongside `codespell`, `check-yaml`, `clang-format`, `ruff`, and `pre-commit.ci` |

---

## 4. Final Takeaway: The Best Path Forward

Steel-manning `pre-commit` reveals a crucial insight: **the hard problem is not the CLI runner—it is making `uncrustify`, `cppcheck`, and `xmllint` available as hermetic, cross-platform binary packages.**

Once you solve that by:
1. Switching `ament_xmllint` from `/usr/bin/xmllint` to Python's prebuilt **`lxml`** wheel (with bundled `package_format2/3.xsd`), and
2. Building prebuilt **PyPI binary wheels via `cibuildwheel`** for `uncrustify` and `cppcheck`,

you get **both** worlds for minimal effort:
* Every `ament_*` linter becomes a 100% hermetic Python wheel installable on Linux (`amd64`/`arm64`), macOS (`arm64`/`amd64`), and Windows (`amd64`) with **zero system dependencies**.
* Repositories can use **`pre-commit` (or `prek`)** hermetically with a 5-line `.pre-commit-config.yaml`.
* And **`manylint`** itself becomes a lightweight, 300-line Python orchestrator package (that depends on those exact pinned wheels to provide `manylint check src/`, `manylint fix src/`, `--output=junit`, and `<export><manylint>` parsing) which can be run via `uvx manylint`, `pre-commit`, or packaged into a standalone executable via `pyinstaller` / `pyoxidizer` without maintaining a complex multi-language Bazel build!
