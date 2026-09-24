# Ament Linters: CLI Check vs. Fix / Reformat Report

Every linter in [`src/ament/ament_lint`](file:///workspaces/ros2/src/ament/ament_lint) provides a standalone command-line executable (`ament_<linter>`) defined via `console_scripts` in its `setup.py` and implemented in `ament_<linter>/main.py`.

---

## 1. Summary: Check-Only vs. Reformat / Auto-Fix Support

Out of the 14 linters in `ament_lint`, **only 2 support `--reformat`**, and **2 others support specialized auto-fix flags**:

| Linter CLI | In `ament_lint_common`? | Supports Check? | Supports Fix / Reformat? | Fix / Reformat CLI Flag(s) |
| :--- | :---: | :---: | :---: | :--- |
| [`ament_uncrustify`](file:///workspaces/ros2/src/ament/ament_lint/ament_uncrustify/ament_uncrustify/main.py#L109-L111) | Yes | Yes | **Yes (Reformat)** | `--reformat` |
| [`ament_clang_format`](file:///workspaces/ros2/src/ament/ament_lint/ament_clang_format/ament_clang_format/main.py#L56-L58) | No | Yes | **Yes (Reformat)** | `--reformat` |
| [`ament_copyright`](file:///workspaces/ros2/src/ament/ament_lint/ament_copyright/ament_copyright/main.py#L67-L77) | Yes | Yes | **Yes (Header Fix)** | `--add-missing <HOLDER> <LICENSE>`<br>`--add-copyright-year [YEAR ...]` |
| [`ament_clang_tidy`](file:///workspaces/ros2/src/ament/ament_lint/ament_clang_tidy/ament_clang_tidy/main.py#L68-L73) | No | Yes | **Yes (Auto-Fix)** | `--fix-errors`<br>`--export-fixes <DAT_FILE>` |
| [`ament_cppcheck`](file:///workspaces/ros2/src/ament/ament_lint/ament_cppcheck/ament_cppcheck/main.py#L55-L97) | Yes | Yes | No (Check only) | — |
| [`ament_cpplint`](file:///workspaces/ros2/src/ament/ament_lint/ament_cpplint/ament_cpplint/main.py#L73-L113) | Yes | Yes | No (Check only) | — |
| [`ament_flake8`](file:///workspaces/ros2/src/ament/ament_lint/ament_flake8/ament_flake8/main.py#L36-L69) | Yes | Yes | No (Check only) | — |
| [`ament_lint_cmake`](file:///workspaces/ros2/src/ament/ament_lint/ament_lint_cmake/ament_lint_cmake/main.py#L35-L59) | Yes | Yes | No (Check only) | — |
| [`ament_pep257`](file:///workspaces/ros2/src/ament/ament_lint/ament_pep257/ament_pep257/main.py#L50-L113) | Yes | Yes | No (Check only) | — |
| [`ament_xmllint`](file:///workspaces/ros2/src/ament/ament_lint/ament_xmllint/ament_xmllint/main.py#L35-L64) | Yes | Yes | No (Check only) | — |
| [`ament_mypy`](file:///workspaces/ros2/src/ament/ament_lint/ament_mypy/ament_mypy/main.py#L30-L91) | No | Yes | No (Check only) | — |
| [`ament_pclint`](file:///workspaces/ros2/src/ament/ament_lint/ament_pclint/ament_pclint/main.py#L32-L82) | No | Yes | No (Check only) | — |
| [`ament_pycodestyle`](file:///workspaces/ros2/src/ament/ament_lint/ament_pycodestyle/ament_pycodestyle/main.py#L27-L60) | No | Yes | No (Check only) | — |
| [`ament_pyflakes`](file:///workspaces/ros2/src/ament/ament_lint/ament_pyflakes/ament_pyflakes/main.py#L30-L51) | No | Yes | No (Check only) | — |

---

## 2. How to Run Linters on the CLI (Outside of Tests)

### Common CLI Conventions Across All `ament_*` Linters
1. **Default `paths` Argument**:
   * Every `ament_*` CLI accepts positional `paths` (`nargs='*'`, `default=['.']`).
   * **No arguments are strictly required** if you run the command from the package or repository root directory—it defaults to recursively scanning the current working directory (`.`) for matching file extensions while automatically skipping hidden/private directories (starting with `.` or `_`) and directories containing `AMENT_IGNORE`.
   * Exception: [`ament_clang_tidy`](file:///workspaces/ros2/src/ament/ament_lint/ament_clang_tidy/ament_clang_tidy/main.py#L49-L54) searches `paths` for `compile_commands.json` files (so you typically pass the `build/` directory or `build/<pkg>/compile_commands.json`, and build with `-DCMAKE_EXPORT_COMPILE_COMMANDS=ON`).
2. **Test vs. CLI Usage (`--xunit-file`)**:
   * When CMake runs a linter in CTest, it passes `--xunit-file <path>.xunit.xml` to write JUnit/XUnit XML results.
   * When running on the CLI interactively, **omit `--xunit-file`**; human-readable diffs/errors are printed directly to `stdout`/`stderr`.
3. **Common Filtering & Config Arguments**:
   * `[paths ...]`: One or more specific files or directories to lint (defaults to `.`).
   * `--exclude <file_or_pattern ...>`: Exclude specific files or directories (supported by `uncrustify`, `copyright`, `cppcheck`, `cpplint`, `flake8`, `pep257`, `xmllint`, `mypy`, `pycodestyle`, `pyflakes`).

---

## 3. CLI Arguments: Checking vs. Reformatting / Fixing

### A. `ament_uncrustify` (C/C++ Code Formatting)
Defined in [`ament_uncrustify/main.py`](file:///workspaces/ros2/src/ament/ament_lint/ament_uncrustify/ament_uncrustify/main.py#L77-L117). Uses Ament's default uncrustify config (`ament_code_style_0_78.cfg` or `ament_code_style_0_72.cfg`) unless overridden.

* **Check for issues (prints unified diff to `stderr`, exits `1` on divergence)**:
  ```bash
  ament_uncrustify
  # Or with optional arguments:
  ament_uncrustify [paths ...] [-c CONFIG_FILE] [--linelength N] [--language {C,C++,CPP}] [--exclude FILE ...]
  ```
* **Reformat in-place to fix issues**:
  ```bash
  ament_uncrustify --reformat [paths ...]
  ```
  *(Note: In [`ament_uncrustify/main.py`](file:///workspaces/ros2/src/ament/ament_lint/ament_uncrustify/main.py#L181-L219), `--reformat` overwrites the files in place, but still exits with return code `1` on the run where divergences were found and fixed. Running it a second time exits with `0`.)*

---

### B. `ament_clang_format` (C/C++ Code Formatting)
Defined in [`ament_clang_format/main.py`](file:///workspaces/ros2/src/ament/ament_lint/ament_clang_format/ament_clang_format/main.py#L36-L64). Uses `ament_clang_format/configuration/.clang-format` by default.

* **Check for issues (prints replacement diffs to `stderr`, exits `1` on divergence)**:
  ```bash
  ament_clang_format [paths ...] [--config PATH] [--clang-format-version VERSION]
  ```
* **Reformat in-place to fix issues (invokes `clang-format -i`)**:
  ```bash
  ament_clang_format --reformat [paths ...]
  ```

---

### C. `ament_copyright` (Copyright & License Headers)
Defined in [`ament_copyright/main.py`](file:///workspaces/ros2/src/ament/ament_lint/ament_copyright/ament_copyright/main.py#L47-L95). Checks `.c`, `.cc`, `.cpp`, `.cxx`, `.h`, `.hh`, `.hpp`, `.hxx`, `.cmake`, and `.py` files.

* **Check for issues**:
  ```bash
  ament_copyright [paths ...] [--exclude FILE ...] [--verbose]
  ```
* **Fix issues (insert missing headers or update copyright years in-place)**:
  ```bash
  # List valid license and copyright holder identifiers:
  ament_copyright --list-licenses
  ament_copyright --list-copyright-names

  # Add missing copyright & license header to files missing them:
  ament_copyright --add-missing "Open Source Robotics Foundation, Inc." apache2 [paths ...]

  # Add current year (or specified years) to existing copyright headers:
  ament_copyright --add-copyright-year [YEAR ...] [paths ...]
  ```

---

### D. `ament_clang_tidy` (C/C++ Static Analysis & Linter)
Defined in [`ament_clang_tidy/main.py`](file:///workspaces/ros2/src/ament/ament_lint/ament_clang_tidy/ament_clang_tidy/main.py#L39-L92). Requires `compile_commands.json` (generated by building with `colcon build --cmake-args -DCMAKE_EXPORT_COMPILE_COMMANDS=ON`).

* **Check for issues**:
  ```bash
  ament_clang_tidy build/<pkg_name> [--config PATH] [--jobs N] [--packages-select PKG ...]
  ```
* **Fix issues in-place (applies `clang-tidy --fix-errors`)**:
  ```bash
  ament_clang_tidy --fix-errors build/<pkg_name>
  # Or export suggested fixes to a YAML/DAT file:
  ament_clang_tidy --export-fixes fixes.yaml build/<pkg_name>
  ```

---

### E. Check-Only Linters (CLI Invocation Reference)

These linters only support checking and reporting issues (no `--reformat` flag in Ament):

1. **`ament_flake8`** ([`ament_flake8/main.py`](file:///workspaces/ros2/src/ament/ament_lint/ament_flake8/ament_flake8/main.py#L40-L69)) — Python style & syntax:
   ```bash
   ament_flake8 [paths ...] [--config PATH] [--linelength N] [--exclude FILE ...]
   ```
2. **`ament_pep257`** ([`ament_pep257/main.py`](file:///workspaces/ros2/src/ament/ament_lint/ament_pep257/ament_pep257/main.py#L60-L113)) — Python docstrings:
   ```bash
   ament_pep257 [paths ...] [--convention {ament,pep257,numpy,google}] [--ignore CODE ...] [--select CODE ...] [--add-ignore CODE ...] [--add-select CODE ...] [--exclude FILE ...]
   ```
3. **`ament_cpplint`** ([`ament_cpplint/main.py`](file:///workspaces/ros2/src/ament/ament_lint/ament_cpplint/ament_cpplint/main.py#L77-L113)) — Google C++ style checker:
   ```bash
   ament_cpplint [paths ...] [--filters FILTER1,FILTER2] [--linelength N] [--root ROOT_DIR] [--exclude FILE ...] [--quiet]
   ```
4. **`ament_cppcheck`** ([`ament_cppcheck/main.py`](file:///workspaces/ros2/src/ament/ament_lint/ament_cppcheck/ament_cppcheck/main.py#L58-L97)) — C/C++ static analysis:
   ```bash
   # Note: Set AMENT_CPPCHECK_ALLOW_SLOW_VERSIONS=1 if using cppcheck 1.88 or 2.x
   AMENT_CPPCHECK_ALLOW_SLOW_VERSIONS=1 ament_cppcheck [paths ...] [--include_dirs DIR ...] [--language {c,c++}] [--libraries LIB ...] [--exclude FILE ...]
   ```
5. **`ament_lint_cmake`** ([`ament_lint_cmake/main.py`](file:///workspaces/ros2/src/ament/ament_lint/ament_lint_cmake/ament_lint_cmake/main.py#L36-L59)) — CMake style checker:
   ```bash
   ament_lint_cmake [paths ...] [--filters FILTER1,FILTER2] [--linelength N]
   ```
6. **`ament_xmllint`** ([`ament_xmllint/main.py`](file:///workspaces/ros2/src/ament/ament_lint/ament_xmllint/ament_xmllint/main.py#L38-L64)) — XML syntax & schema validator:
   ```bash
   ament_xmllint [paths ...] [--extensions EXT ...] [--exclude FILE_OR_DIR ...]
   ```
7. **`ament_mypy`** ([`ament_mypy/main.py`](file:///workspaces/ros2/src/ament/ament_lint/ament_mypy/ament_mypy/main.py#L32-L91)) — Python static type checking:
   ```bash
   ament_mypy [paths ...] [--config PATH | --ament-strict] [--exclude FILE ...] [--cache-dir DIR]
   ```
8. **`ament_pycodestyle`** ([`ament_pycodestyle/main.py`](file:///workspaces/ros2/src/ament/ament_lint/ament_pycodestyle/ament_pycodestyle/main.py#L31-L60)) — Python PEP 8 style checker:
   ```bash
   ament_pycodestyle [paths ...] [--config PATH] [--linelength N] [--exclude FILE ...]
   ```
9. **`ament_pyflakes`** ([`ament_pyflakes/main.py`](file:///workspaces/ros2/src/ament/ament_lint/ament_pyflakes/ament_pyflakes/main.py#L31-L51)) — Python unused imports/variables checker:
   ```bash
   ament_pyflakes [paths ...] [--exclude FILE ...]
   ```
10. **`ament_pclint`** ([`ament_pclint/main.py`](file:///workspaces/ros2/src/ament/ament_lint/ament_pclint/ament_pclint/main.py#L35-L82)) — Commercial C/C++ static analysis:
    ```bash
    ament_pclint [paths ...] [--language {c,cpp}] [--pclint-config-file CFG] [--include-directories DIR ...] [--compiler-definitions DEF ...]
    ```
