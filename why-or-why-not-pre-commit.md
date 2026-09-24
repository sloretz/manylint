# `manylint` vs. `pre-commit`: Strengths, Weaknesses, and Which Approach Is Better

A very natural question when designing `manylint` is: **Why not just use [`pre-commit`](https://pre-commit.com/) (or its Rust reimplementation, [`prek`](https://github.com/j178/prek))?**

Several large ROS 2 projects (such as MoveIt 2, Nav2, and `ros2_control`) already use `.pre-commit-config.yaml` for parts of their linting workflow. Below is a candid engineering comparison of where `pre-commit` excels, where it falls short in the ROS 2 ecosystem, and how to decide between the two approaches.

---

## 1. How `pre-commit` Works

`pre-commit` is a multi-language hook manager configured via a `.pre-commit-config.yaml` file at the **root of a Git repository**:
* Each entry points to a hook repository URL and a pinned Git tag (`rev:`).
* On first execution, `pre-commit` clones each hook repo into `~/.cache/pre-commit/` and creates an isolated environment (e.g., a Python `virtualenv` via `pip` or a Node/Rust/Go environment) for that hook.
* It passes the list of staged (or all) filenames in the Git repository as positional arguments to each hook's `entry` command.

---

## 2. Strengths of `pre-commit` (Why You Might Choose `pre-commit`)

1. **Already Exists & Zero Custom Build Maintenance**:
   * Building and maintaining a custom Bazel static binary that bundles `uncrustify`, `cppcheck`, `libxml2`, `clang-format`, and an embedded Python runtime across 5 OS/architecture targets requires ongoing maintenance.
   * `pre-commit` is already mature, widely understood by developers, and maintained by a large open-source community.
2. **Easy Version Pinning for Tools Published as PyPI Binary Wheels**:
   * Tools like `ruff`, `flake8`, `black`, `cmake-format`, and even `clang-format` (which is published as a prebuilt binary wheel on PyPI via `mirrors-clang-format`) work hermetically in `pre-commit` across Linux, macOS, and Windows without system `apt` packages.
3. **Rich Ecosystem of Non-ROS Hygiene Hooks**:
   * Out of the box, `.pre-commit-config.yaml` gives you hooks that `ament_lint` doesn't cover: `codespell` (typos), `check-yaml`, `check-merge-conflict`, `check-added-large-files`, `end-of-file-fixer`, `trailing-whitespace`, and `shellcheck`.
4. **Native Git Hook Lifecycle & `pre-commit.ci`**:
   * `pre-commit install` automatically wires up `.git/hooks/pre-commit`, and GitHub repositories can use `pre-commit.ci` to automatically push formatting fixes to pull requests.

---

## 3. Weaknesses of `pre-commit` for ROS 2 (Why `manylint` Exists)

While `pre-commit` is great for a single standalone Git repository using `clang-format` and `ruff`, it runs into **five structural problems** when applied to ROS 2 / Ament workspaces:

### Problem 1: Config Duplication Across 100+ Git Repos & Multi-Package Repos
* **ROS 2 Workspaces Are Multi-Repo (`vcstool`)**:
  * A ROS 2 workspace (`/workspaces/ros2/src`) is not a single Git repository—it is a folder containing **100+ separate Git repositories** (`rclcpp`, `rcl`, `rcutils`, `rmw`, `ament_lint`, `rviz`, `rqt_*`) containing **400+ ROS packages**.
  * Running `pre-commit run --all-files` at `/workspaces/ros2/src` immediately fails with `FatalError: /workspaces/ros2/src is not a git repository`.
* **Every Git Repo Must Duplicate `.pre-commit-config.yaml` + Linter Configs**:
  * With `pre-commit`, every single one of those 100+ Git repositories must commit its own `.pre-commit-config.yaml` **plus** copies of `ament_code_style.cfg`, `.clang-format`, and `.flake8`.
  * Whenever ROS 2 updates a standard linter version or rule across a ROS distro, maintainers must open and merge **100+ pull requests across 100+ repositories**.
* **Multi-Package Git Repositories Lack Per-Package Granularity**:
  * A single Git repo often contains 5 to 30 ROS packages (e.g. `src/ament/ament_lint` has 30 packages; `src/ros2/rclcpp` has 4 packages).
  * Because `.pre-commit-config.yaml` lives at the Git repo root and knows nothing about `package.xml`, per-package customizations (`<export><manylint>`) must be written as brittle, repo-wide regular expressions (`exclude: ^(pkg_a/include/generated/.*|pkg_b/.*)$`) in the root YAML file.

### Problem 2: `uncrustify`, `cppcheck`, and `xmllint` Are NOT Hermetic in `pre-commit`
* Unlike `clang-format` and `flake8`, **`uncrustify`, `cppcheck`, and `xmllint` do not publish official multi-platform binary wheels on PyPI**.
* Consequently, in ROS 2 projects that use `pre-commit` today:
  * They either configure `uncrustify`, `cppcheck`, and `xmllint` with `language: system` (which falls back to `/usr/bin/uncrustify` and `/usr/bin/cppcheck` from `apt`—meaning **you still have system dependencies and version drift between Ubuntu 22.04 and 24.04!**),
  * Or they use a `pre-commit` hook that compiles `uncrustify` from C++ source via CMake on the developer's machine (which requires a local C++ compiler and CMake, and frequently fails on macOS/Windows).
* `manylint` compiles `uncrustify`, `cppcheck`, and `libxml2` (`xmllint` + embedded `package_format2/3.xsd` schemas) **statically into the binary itself**, guaranteeing identical behavior with zero system dependencies.

### Problem 3: `pre-commit` Has No Separation Between `check` and `fix`
* In `.pre-commit-config.yaml`, each hook has a single static `args:` list:
  * If you configure the hook with `--replace` / `-i` (auto-fix mode), then running `pre-commit` **always modifies files on disk**. You cannot run a read-only check without mutating the working tree.
  * If you configure the hook with `--check` / `--dry-run --Werror` (check-only mode), then developers **cannot use `pre-commit` to auto-format their code**!
* `manylint` natively separates `manylint check` (read-only verification + diff output) and `manylint fix` (in-place auto-formatting) using the exact same configuration.

### Problem 4: No JUnit XML Output (`--output=junit`) for ROS 2 CI
* `pre-commit` only prints human-readable text to `stdout`. It cannot generate aggregated JUnit XML (`--output=junit`) or per-package `<pkg>/<linter>.xunit.xml` files (`--junit-dir`) for `colcon test-result`, Jenkins, or GitLab CI test dashboards.

### Problem 5: System Python Dependency & First-Run Network Overhead
* `pre-commit` itself requires a working system Python + `pip`/`virtualenv` installation, and on first run in a fresh container or CI job it downloads and builds multiple virtual environments in `~/.cache/pre-commit/` (often 500 MB+).
* `manylint` is a single static binary installed via `curl ... | bash` that runs offline with zero environment creation overhead.

---

## 4. Side-by-Side Comparison

| Feature / Requirement | `pre-commit` | `manylint` |
| :--- | :--- | :--- |
| **Granularity** | Per Git repository (`.pre-commit-config.yaml`) | Per ROS package (`package.xml`), per directory, or entire `src/` workspace |
| **Works across a `vcstool` `src/` folder (100+ repos)?** | No (must run inside each Git repo separately) | **Yes** (`manylint check src/` / `manylint fix src/`) |
| **Zero config needed in standard ROS 2 packages?** | No (every Git repo needs `.pre-commit-config.yaml` + `.cfg` files) | **Yes** (ROS 2 default configs are baked into the binary) |
| **Hermetic `uncrustify`, `cppcheck`, `xmllint`?** | No (relies on `language: system` `apt` binaries or local source build) | **Yes** (statically linked inside `manylint`) |
| **Offline `package.xml` XSD schema validation?** | No (`xmllint` fetches `http://download.ros.org/schema/...` over network) | **Yes** (`package_format2/3.xsd` embedded in binary) |
| **Separate `check` (read-only) vs. `fix` (in-place) modes?** | No (a hook in YAML is either always-fix or always-check) | **Yes** (`manylint check` vs. `manylint fix`) |
| **JUnit XML output (`--output=junit`) for CI?** | No | **Yes** (aggregated XML and `colcon test-result` directory) |
| **Non-ROS general hooks (`codespell`, `check-yaml`, etc.)?** | **Yes** (massive ecosystem) | No (focused on ROS 2 / Ament linters) |
| **Engineering effort to build & maintain?** | **Low** (use upstream `pre-commit`) | **Medium–High** (maintain Bazel static binary build) |

---

## 5. Verdict: Which Is the Better Approach?

### Choose `pre-commit` alone if:
* You only care about **individual, self-contained Git repositories** (not workspace-wide `src/` runs across 100+ repos).
* You are willing to **drop `uncrustify` and `ament_copyright`** in favor of `clang-format` and `ruff` (which have official prebuilt binary wheels on PyPI and therefore work hermetically in `pre-commit`).
* You don't mind committing a `.pre-commit-config.yaml` and `.clang-format` to every Git repository, and you don't need JUnit XML reports.

### Choose `manylint` if:
* You want to replace `ament_lint_auto` / `colcon test` linter tests across the **ROS 2 ecosystem** without adding `.pre-commit-config.yaml` and linter `.cfg` files to hundreds of repositories.
* You need **true zero-dependency hermeticity for C/C++ and XML tools** (`uncrustify`, `cppcheck`, `xmllint` with ROS XSD schemas, `cpplint`, `ament_copyright`, `flake8` + its 7 plugins) across Linux, macOS, and Windows.
* You want package maintainers to configure overrides in `package.xml` (`<export><manylint>`) rather than maintaining regex exclusions in a repo-root YAML file.
* You need both `manylint check --output=junit` (for CI test reporting) and `manylint fix` (for developers).

### Best of Both Worlds: Make `manylint` Usable *Inside* `pre-commit`!
These two tools do not have to be mutually exclusive. By adding a tiny `.pre-commit-hooks.yaml` to the `manylint` GitHub repository:

```yaml
# .pre-commit-hooks.yaml in the manylint repo
- id: manylint-fix
  name: manylint (auto-fix ROS packages)
  entry: manylint fix --git-staged
  language: system
  pass_filenames: false

- id: manylint-check
  name: manylint (check ROS packages)
  entry: manylint check --git-staged
  language: system
  pass_filenames: false
```

1. **ROS 2 CI and developers** can use `manylint check src/` and `manylint fix src/` directly with zero config files in their repositories.
2. **Teams that already use `pre-commit`** (for `codespell`, `check-yaml`, etc.) can simply add `manylint` as a single hook in their `.pre-commit-config.yaml`—getting hermetic `uncrustify`, `cppcheck`, `xmllint`, `flake8`, and `package.xml`-aware linting without maintaining 10 separate hooks in YAML.
