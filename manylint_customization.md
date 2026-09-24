# Customizing `manylint` via `.pre-commit-config.yaml`

Instead of inventing a custom `<export><manylint>` XML schema inside `package.xml`, **`manylint` uses `.pre-commit-config.yaml` as its native customization format**:

1. **If no `.pre-commit-config.yaml` is present** in a repository (or package directory):
   * `manylint` automatically uses its **built-in default configuration** (`default_pre_commit_config.yaml`), running the standard ROS 2 / Ament linters (`copyright`, `cppcheck`, `cpplint`, `flake8`, `lint_cmake`, `pep257`, `uncrustify`, `xmllint`) with ROS 2's canonical style configs.
   * **Zero configuration files are required** in standard ROS 2 repositories.
2. **If a `.pre-commit-config.yaml` is present**:
   * `manylint` uses that `.pre-commit-config.yaml` to determine which linters/hooks run, which files are excluded, and what custom config files or CLI arguments are passed.

---

## 1. What `.pre-commit-config.yaml` Controls

Every customization need is handled natively by `.pre-commit-config.yaml` syntax:

* **Which linters run**: Listed under `hooks:` (`- id: uncrustify`, `- id: flake8`, etc.). To disable a default linter, simply omit it from `hooks:`. To enable an optional linter (like `clang-format`, `clang-tidy`, `mypy`, or `codespell`), add its `- id:`.
* **Global file exclusions**: Top-level `exclude: <regex>` at the root of `.pre-commit-config.yaml`.
* **Per-linter file filtering**: Hook-level `exclude: <regex>` or `files: <regex>`.
* **Custom linter config files & CLI arguments**: Hook-level `args: [...]` pointing to the linter's native config file (e.g., `args: ["-c", "custom_uncrustify.cfg"]` or `args: ["--config=.flake8"]`).

---

## 2. Example `.pre-commit-config.yaml`

```yaml
# Global regex of files/directories to exclude across all linters
exclude: ^(src/third_party/|include/generated/)

repos:
  - repo: https://github.com/sloretz/manylint
    rev: v0.2.0
    hooks:
      # 1. Copyright checker / fixer
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

      # 8. XML schema & formatting linter
      - id: xmllint
```

---

## 3. Built-In Hook IDs Provided by `manylint`

| Hook `id` | Default? | Supports `manylint fix`? | Native Config / `args` Example |
| :--- | :---: | :---: | :--- |
| **`copyright`** | Yes | **Yes** | `args: ["--add-missing", "<HOLDER>", "apache2"]` |
| **`cppcheck`** | Yes | No (Check only) | `args: ["-I", "include", "--language=c++"]` |
| **`cpplint`** | Yes | No (Check only) | Reads `CPPLINT.cfg` or `args: ["--linelength=120"]` |
| **`flake8`** | Yes | No (Check only) | `args: ["--config=.flake8"]` |
| **`lint_cmake`** | Yes | No (Check only) | `args: ["--linelength=140"]` |
| **`pep257`** | Yes | No (Check only) | `args: ["--convention=google"]` |
| **`uncrustify`** | Yes | **Yes** | `args: ["-c", "uncrustify.cfg"]` |
| **`xmllint`** | Yes | **Yes** | Validates `<?xml-model?>` XSDs & formats XML |
| **`clang-format`** | No | **Yes** | `args: ["--config=.clang-format"]` |
| **`clang-tidy`** | No | **Yes** | `args: ["--config=.clang-tidy"]` |
| **`mypy`** | No | No (Check only) | `args: ["--config=mypy.ini"]` |
| **`ruff`** | No | **Yes** | `args: ["--config=ruff.toml"]` |
