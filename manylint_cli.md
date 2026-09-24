# `manylint` — Standalone Multi-Linter CLI Specification for ROS 2

`manylint` is a unified command-line interface that discovers ROS 2 packages under given filesystem paths and runs all applicable linters and formatters directly—decoupling code quality checks and auto-formatting from CMake/CTest execution.

---

## 1. Synopsis

```text
manylint <subcommand> [options] [paths ...]
```

### Subcommands
* **`manylint check [paths ...]`**: Run linters in read-only verification mode across one or more ROS packages or directories.
* **`manylint fix [paths ...]`**: Run auto-formatters and fixers in-place on all supported linters, then check for any remaining unfixable issues.
* **`manylint list [paths ...]`**: List discovered ROS 2 packages under `paths` and the linters that will be executed for each package.

*(If `[paths ...]` is omitted, `manylint` defaults to `.`, the current working directory.)*

---

## 2. Path-Based Target Selection & Workflows

Targets are selected purely by filesystem path (`[paths ...]`), optionally filtered by Git working tree state (`--git-diff` or `--git-staged`).

### A. Single Package (`path/to/pkg`)
When given a path containing a `package.xml` (or a subdirectory/file inside a package):
```bash
# Check all applicable linters on a single ROS package
manylint check src/ros2/rclcpp/rclcpp

# Auto-fix all fixable issues (uncrustify/clang-format, copyright, xmllint, etc.)
manylint fix src/ros2/rclcpp/rclcpp
```

### B. Multi-Package Directory (`path/to/folder`)
When given a directory containing multiple ROS packages in its subdirectories, `manylint` recursively discovers every ROS package under that folder (skipping directories containing `AMENT_IGNORE` or `COLCON_IGNORE`):
```bash
# Check every ROS package under src/
manylint check src/

# Fix all fixable issues across every ROS package under src/
manylint fix src/
```

### C. Behavior of `manylint fix`
When `manylint fix` runs on a package:
1. **Formatters / Fixers run in-place**:
   * **C/C++ style**: `uncrustify` (or `clang_format`) reformats `.c/.cpp/.h/.hpp` files.
   * **XML formatting**: `xmllint --format` normalizes XML indentation.
   * **Copyright headers**: `copyright` updates copyright years or inserts missing headers.
   * **Python style**: `autopep8` / `ruff` fixes PEP 8 formatting and unused imports.
2. **Post-fix status & exit code**:
   * Reports which files were modified and any remaining unfixable violations from check-only linters (e.g., `cppcheck`, `cpplint`, `flake8`, `pep257`, `lint_cmake`).

---

## 3. CLI Options

### A. Linter Selection
* **`-l, --linters <linter,linter,...>`**: Run only the specified comma-separated linters (e.g., `manylint check --linters uncrustify,cpplint src/`). If omitted, all applicable default linters for each package are run.

### B. Git Incremental Filtering
* **`--git-diff [REF]`**: Only check or fix files modified relative to `REF` (defaults to `HEAD` if `REF` is omitted) within the given `paths`.
* **`--git-staged`**: Only check or fix files currently staged in the Git index (`git diff --cached`), ideal for pre-commit hooks.

### C. Output Formats (`--output=text` | `--output=junit`)
* **`--output {text,junit}`**:
  * `text` *(default)*: Human-readable output grouped by ROS package and linter, showing file/line diagnostics, unified diffs, and a summary count.
  * `junit`: JUnit/XUnit XML report representing results across all checked ROS packages and linters.
* **`--junit-file <path>`**: Write the aggregated JUnit XML output to `<path>` (instead of `stdout`).
* **`--junit-dir <dir>`**: Write per-package XUnit XML files into `<dir>/<pkg_name>/<linter>.xunit.xml` (compatible with `colcon test-result`).

### D. General Execution & Filtering Options
* **`--exclude <glob ...>`**: Exclude files or directories matching the given glob patterns.
* **`-j, --jobs <N>`**: Number of parallel worker processes (defaults to `0` = number of CPU cores).

---

## 4. Handling `--output=junit` Across Multiple ROS Packages

When running `manylint check` across multiple packages (`manylint check src/ --output=junit`), `manylint` supports two ways to consume JUnit XML:

### Mode 1: Aggregated Multi-Package JUnit XML (`--output=junit` or `--junit-file=<path>`)
Outputs a single JUnit XML document (to `stdout` by default, or to `<path>` when `--junit-file` is passed):
* The root `<testsuites>` element aggregates statistics (`tests`, `failures`, `errors`, `time`) across all checked ROS packages.
* Each `(package, linter)` pair is emitted as a `<testsuite name="<pkg_name>.<linter>" package="<pkg_name>">`.
* Each checked file is emitted as a `<testcase classname="<pkg_name>.<linter>" name="<relative_file_path>">`.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<testsuites name="manylint" tests="142" failures="2" errors="0" time="3.41">
  <testsuite name="rclcpp.uncrustify" package="rclcpp" tests="45" failures="1" time="1.12">
    <testcase classname="rclcpp.uncrustify" name="src/rclcpp/node.cpp" time="0.02">
      <failure message="Code style divergence in src/rclcpp/node.cpp">
<![CDATA[
--- src/rclcpp/node.cpp
+++ src/rclcpp/node.cpp.uncrustify
@@ -42,1 +42,1 @@
-void foo( int x ){
+void foo(int x) {
]]>
      </failure>
    </testcase>
  </testsuite>
  <testsuite name="rclcpp.xmllint" package="rclcpp" tests="1" failures="0" time="0.05">
    <testcase classname="rclcpp.xmllint" name="package.xml" time="0.05"/>
  </testsuite>
  <testsuite name="rclpy.flake8" package="rclpy" tests="28" failures="1" time="0.84">
    <!-- ... -->
  </testsuite>
</testsuites>
```

### Mode 2: Per-Package JUnit Directory (`--output=junit --junit-dir=<dir>`)
Writes separate XUnit files per package and linter using Ament's standard directory structure (`<dir>/<pkg_name>/<linter>.xunit.xml`), allowing `colcon test-result` to summarize results across all packages:
```text
<junit-dir>/
├── rclcpp/
│   ├── copyright.xunit.xml
│   ├── cppcheck.xunit.xml
│   ├── cpplint.xunit.xml
│   ├── lint_cmake.xunit.xml
│   ├── uncrustify.xunit.xml
│   └── xmllint.xunit.xml
└── rclpy/
    ├── copyright.xunit.xml
    ├── flake8.xunit.xml
    ├── pep257.xunit.xml
    └── xmllint.xunit.xml
```

---

## 5. Example CLI Invocations

```bash
# 1. Check a single ROS package
manylint check src/ros2/rclcpp/rclcpp

# 2. Check all ROS packages under src/
manylint check src/

# 3. Run only uncrustify and cpplint on src/ros2/rclcpp
manylint check --linters uncrustify,cpplint src/ros2/rclcpp

# 4. Fix all fixable issues in files changed since origin/rolling
manylint fix --git-diff origin/rolling src/

# 5. Fix staged files in a git pre-commit hook
manylint fix --git-staged

# 6. Run in CI and emit JUnit XML
manylint check --output=junit --junit-file=build/manylint_results.xml src/
```

---

## 6. Exit Codes

| Exit Code | Meaning in `manylint check` | Meaning in `manylint fix` |
| :---: | :--- | :--- |
| `0` | All linters passed with zero violations | All violations were fixed (or none existed) |
| `1` | One or more linter violations were found | Unfixable linter violations remain after fixing |
| `2` | Invalid CLI arguments or runtime error | Invalid CLI arguments or runtime error |
