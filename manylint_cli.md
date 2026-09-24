# `manylint` — Standalone Multi-Repo `pre-commit` CLI Specification for ROS 2

`manylint` is a unified command-line tool that runs `pre-commit` across one or more ROS 2 packages or multi-repository directories (such as `src/`), using pinned linter versions and a built-in default `.pre-commit-config.yaml` when a repository does not provide its own.

Following `pre-commit`'s philosophy, **there is no separate `check` vs. `fix` subcommand**:
* Linters that support auto-fixing (`uncrustify`, `clang-format`, `xmllint`) **automatically fix files in-place** and report a failure (exit code `1` + diff) on the pass where files were modified.
* Linters that only check (`cppcheck`, `cpplint`, `flake8`, `pep257`, `lint_cmake`, `copyright`) **check and report violations** (exit code `1`).
* Both locally and in CI, you run the exact same command: `manylint [paths ...]`.

---

## 1. Synopsis

```text
manylint [options] [paths ...]
```

*(If `[paths ...]` is omitted, `manylint` defaults to `.`, the current working directory.)*

---

## 2. Core Workflows

### A. Single Repository or Package (`path/to/pkg`)
```bash
# Run all applicable linters (auto-fixing where supported) on a single package or repo
manylint src/ros2/rclcpp/rclcpp
```

### B. Multi-Repository Workspace (`path/to/folder`)
When given a workspace directory containing multiple Git repositories or ROS packages in its subdirectories, `manylint` discovers every repository/package under that folder (skipping directories containing `AMENT_IGNORE` or `COLCON_IGNORE`):
```bash
# Run across every Git repository / ROS package under src/
manylint src/
```

### C. What Happens on Execution (Local vs. CI)
1. **Local Development**:
   * Running `manylint src/` automatically formats C/C++ (`uncrustify --reformat`) and XML (`xmllint --format`) files in-place, and reports any remaining check errors (`flake8`, `cppcheck`, `cpplint`, `pep257`, `lint_cmake`, `copyright`).
   * If any file was modified or had a violation, `manylint` exits `1`. Running `manylint src/` a second time after auto-formatting exits `0` once all issues are resolved.
2. **Continuous Integration (CI)**:
   * Running `manylint --output=junit src/` runs the exact same hooks.
   * If any file was modified by an auto-formatter (meaning uncommitted formatting divergences existed) or failed a check-only linter, `manylint` records the failure and unified diff in the JUnit XML report and exits `1`.

---

## 3. CLI Options

### A. Linter / Hook Selection
* **`-l, --linters <hook_id,hook_id,...>`**: Run only the specified comma-separated `pre-commit` hook IDs (e.g., `manylint --linters uncrustify,cpplint src/`). If omitted, all hooks in `.pre-commit-config.yaml` (or the built-in default config) are run.

### B. Git Incremental Filtering
* **`--git-diff [REF]`**: Only run on files modified relative to `REF` (defaults to `HEAD` if `REF` is omitted) within the given `paths` (passes `--from-ref <REF> --to-ref HEAD` to `pre-commit`).
* **`--git-staged`**: Only run on files currently staged in the Git index (default `pre-commit` staged behavior, ideal for git pre-commit hooks).

### C. Output Formats (`--output=text` | `--output=junit`)
* **`--output {text,junit}`**:
  * `text` *(default)*: Human-readable output grouped by repository/package and hook, showing diagnostics, unified diffs (`--show-diff-on-failure`), and a summary count.
  * `junit`: JUnit/XUnit XML report representing results across all checked repositories/packages and hooks.
* **`--junit-file <path>`**: Write the aggregated JUnit XML output to `<path>` (instead of `stdout`).
* **`--junit-dir <dir>`**: Write per-package/per-repo XUnit XML files into `<dir>/<name>/<hook_id>.xunit.xml` (compatible with `colcon test-result`).

### D. General Options
* **`--exclude <regex>`**: Additional file/directory regex exclusion pattern.
* **`-j, --jobs <N>`**: Number of repositories to process in parallel (defaults to `0` = number of CPU cores).

---

## 4. Handling `--output=junit` Across Multiple Repositories / Packages

### Mode 1: Aggregated Multi-Repo JUnit XML (`--output=junit` or `--junit-file=<path>`)
Outputs a single JUnit XML document (to `stdout` by default, or to `<path>` when `--junit-file` is passed):
* The root `<testsuites>` element aggregates statistics (`tests`, `failures`, `errors`, `time`) across all targets.
* Each `(target, hook_id)` pair is emitted as a `<testsuite name="<target>.<hook_id>" package="<target>">`.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<testsuites name="manylint" tests="142" failures="1" errors="0" time="3.41">
  <testsuite name="rclcpp.uncrustify" package="rclcpp" tests="45" failures="1" time="1.12">
    <testcase classname="rclcpp.uncrustify" name="src/rclcpp/node.cpp" time="0.02">
      <failure message="Code style divergence (file modified by uncrustify)">
<![CDATA[
--- src/rclcpp/node.cpp
+++ src/rclcpp/node.cpp
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
</testsuites>
```

### Mode 2: Per-Package JUnit Directory (`--output=junit --junit-dir=<dir>`)
Writes separate XUnit files per target and hook (`<dir>/<target>/<hook_id>.xunit.xml`), allowing `colcon test-result` to summarize results across a workspace.

---

## 5. Example CLI Invocations

```bash
# 1. Lint and auto-fix a single ROS package
manylint src/ros2/rclcpp/rclcpp

# 2. Lint and auto-fix all repositories/packages under src/
manylint src/

# 3. Run only uncrustify and cpplint on src/ros2/rclcpp
manylint --linters uncrustify,cpplint src/ros2/rclcpp

# 4. Run on files changed since origin/rolling
manylint --git-diff origin/rolling src/

# 5. Run on staged files in the current repository
manylint --git-staged

# 6. Run in CI and emit JUnit XML
manylint --output=junit --junit-file=build/manylint_results.xml src/
```

---

## 6. Exit Codes

| Exit Code | Meaning |
| :---: | :--- |
| `0` | All hooks passed with zero violations and no files needed modification |
| `1` | One or more hooks found violations or modified files in-place |
| `2` | Invalid CLI arguments or runtime error |
