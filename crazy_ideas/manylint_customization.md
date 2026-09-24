# Customizing `manylint` via `.pre-commit-config.yaml`

`manylint` uses standard `.pre-commit-config.yaml` files as its customization mechanism:

1. **If no `.pre-commit-config.yaml` is present** in a repository:
   * `manylint` automatically uses its **built-in default configuration** (`default_pre_commit_config.yaml`), running the standard ROS 2 / Ament linters (`copyright`, `cppcheck`, `cpplint`, `flake8`, `lint_cmake`, `pep257`, `uncrustify`, `xmllint`) with ROS 2's canonical style configs.
   * **Zero configuration files are required** in standard ROS 2 repositories.
2. **If a `.pre-commit-config.yaml` is present**:
   * `manylint` uses that `.pre-commit-config.yaml` to determine which linters/hooks run, which files are excluded, and what custom config files or CLI arguments are passed.

---

## 1. How Linters Behave (Auto-Fix vs. Check-Only)

Following `pre-commit`'s standard model, hooks do not need separate `check` and `fix` configurations:
* **Auto-fixing hooks (`uncrustify`, `clang-format`, `xmllint`, `ruff`)**: Always format files in-place (`--reformat` / `-i` / `--format`) and exit `1` when files are modified. Locally, this fixes formatting automatically; in CI (`manylint --output=junit`), any modified file fails the check and reports the diff.
* **Check-only hooks (`cppcheck`, `cpplint`, `flake8`, `pep257`, `lint_cmake`, `copyright`, `mypy`)**: Check files and exit `1` when violations are found (unless auto-fix flags like `--add-missing` are passed in `args:`).

---

## 2. Example `.pre-commit-config.yaml`

```yaml
# Global regex of files/directories to exclude across all hooks
exclude: ^(src/third_party/|include/generated/)

repos:
  - repo: https://github.com/sloretz/manylint
    rev: v0.2.0
    hooks:
      # 1. Copyright checker (or auto-add missing headers with args)
      - id: copyright
        args: ["--add-missing", "Open Source Robotics Foundation, Inc.", "apache2"]

      # 2. Cppcheck static analysis with custom include directory
      - id: cppcheck
        exclude: ^test/benchmark_
        args: ["-I", "include", "--language=c++"]

      # 3. Cpplint with custom line length
      - id: cpplint
        args: ["--linelength=120"]

      # 4. Flake8 with custom .flake8 config file
      - id: flake8
        args: ["--config=.flake8"]

      # 5. CMake linter
      - id: lint_cmake

      # 6. PEP 257 docstring linter
      - id: pep257

      # 7. Replaced default uncrustify with clang-format using repo's .clang-format
      - id: clang-format
        args: ["--config=.clang-format"]

      # 8. XML schema validator & auto-formatter
      - id: xmllint
```

---

## 3. Built-In Hook IDs Provided by `manylint`

| Hook `id` | In Default Config? | Behavior When Invoked | Native Config / `args` Example |
| :--- | :---: | :--- | :--- |
| **`uncrustify`** | Yes | **Auto-formats C/C++ in-place** (`--reformat`) | `args: ["-c", "uncrustify.cfg"]` |
| **`xmllint`** | Yes | **Validates XSD schemas & formats XML in-place** | `args: ["--extensions", "xml", "launch"]` |
| **`copyright`** | Yes | Checks headers (or adds missing if `--add-missing` in `args`) | `args: ["--add-missing", "<HOLDER>", "apache2"]` |
| **`cppcheck`** | Yes | Static analysis check | `args: ["-I", "include", "--language=c++"]` |
| **`cpplint`** | Yes | Google C++ style check | Reads `CPPLINT.cfg` or `args: ["--linelength=120"]` |
| **`flake8`** | Yes | Python PEP 8 & syntax check | `args: ["--config=.flake8"]` |
| **`lint_cmake`** | Yes | CMake style check | `args: ["--linelength=140"]` |
| **`pep257`** | Yes | Python docstring check | `args: ["--convention=google"]` |
| **`clang-format`** | No | **Auto-formats C/C++ in-place** (`--reformat`) | `args: ["--config=.clang-format"]` |
| **`clang-tidy`** | No | Static analysis & `--fix-errors` | `args: ["--config=.clang-tidy"]` |
| **`mypy`** | No | Python static type check | `args: ["--config=mypy.ini"]` |
| **`ruff`** | No | **Auto-fixes Python imports/style in-place** (`--fix`) | `args: ["--config=ruff.toml"]` |
