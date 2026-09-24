# Direct CLI Usage of Underlying Linter Tools (Without Ament Wrappers)

This report explains what underlying tools power the 14 `ament_lint` packages, what configurations and flags Ament passes to them under the hood, and how to invoke the underlying tools directly from the CLI to **check** for issues and **reformat/fix** code without using `ament_*` wrappers.

---

## 1. Overview of Underlying Tools & Capabilities

The 14 Ament linters fall into three categories based on how they are implemented:
1. **External Native Binaries**: `uncrustify`, `clang-format`, `clang-tidy`, `cppcheck`, `xmllint`, `pclp64_linux` (PC-lint).
2. **External Python Packages/CLIs**: `flake8`, `pydocstyle` (powers `ament_pep257`), `mypy`, `pycodestyle`, `pyflakes`.
3. **Vendored / Native Python Modules in `ament_lint`**:
   * [`cpplint.py`](file:///workspaces/ros2/src/ament/ament_lint/ament_cpplint/ament_cpplint/cpplint.py) (vendored inside `ament_cpplint`, also available upstream via `pip install cpplint`).
   * [`cmakelint.py`](file:///workspaces/ros2/src/ament/ament_lint/ament_lint_cmake/ament_lint_cmake/cmakelint.py) (vendored inside `ament_lint_cmake`, also available upstream via `pip install cmakelint`).
   * [`ament_copyright`](file:///workspaces/ros2/src/ament/ament_lint/ament_copyright/ament_copyright/main.py) (written natively in Python for ROS 2; no separate upstream tool).

| Ament Wrapper | Underlying CLI Tool | Native Check Support? | Native Fix / Reformat Support? | Companion Auto-Fixer (if check-only) |
| :--- | :--- | :---: | :---: | :--- |
| `ament_uncrustify` | `uncrustify` | Yes (`--check`) | **Yes** (`--replace --no-backup`) | — |
| `ament_clang_format` | `clang-format` | Yes (`--dry-run --Werror`) | **Yes** (`-i`) | — |
| `ament_clang_tidy` | `clang-tidy` | Yes | **Yes** (`-fix` / `-fix-errors`) | — |
| `ament_xmllint` | `xmllint` | Yes (`--noout`) | **Yes** (`--format -o <file>`) | — |
| `ament_copyright` | `python3 -m ament_copyright.main` | Yes | **Yes** (`--add-missing`, `--add-copyright-year`) | `reuse` / `licenseheaders` |
| `ament_cppcheck` | `cppcheck` | Yes | No | `clang-tidy -fix` |
| `ament_cpplint` | `cpplint` | Yes | No | `uncrustify` / `clang-format` |
| `ament_flake8` | `flake8` | Yes | No | `autopep8` / `ruff check --fix` / `black` |
| `ament_pep257` | `pydocstyle` | Yes | No | `docformatter --in-place` / `ruff` |
| `ament_lint_cmake` | `cmakelint` | Yes | No | `cmake-format -i` |
| `ament_mypy` | `mypy` | Yes | No | — |
| `ament_pycodestyle` | `pycodestyle` | Yes | No | `autopep8 --in-place` |
| `ament_pyflakes` | `pyflakes` | Yes | No | `autoflake --in-place` / `ruff check --fix` |
| `ament_pclint` | `pclp64_linux` | Yes | No | — |

---

## 2. Calling Underlying C / C++ Tools Directly

### A. `uncrustify` (Underlying tool for `ament_uncrustify`)
* **ROS 2 Config File**: [`src/ament/ament_lint/ament_uncrustify/ament_uncrustify/configuration/ament_code_style_0_78.cfg`](file:///workspaces/ros2/src/ament/ament_lint/ament_uncrustify/ament_uncrustify/configuration/ament_code_style_0_78.cfg) (or `ament_code_style_0_72.cfg` for uncrustify < 0.78.1).
* **Important Quirk**: [`ament_uncrustify/main.py`](file:///workspaces/ros2/src/ament/ament_lint/ament_uncrustify/ament_uncrustify/main.py#L74-L75) passes `-l C` for `.c`, `.cc`, `.h`, `.hh` and `-l CPP` for `.cpp`, `.cxx`, `.hpp`, `.hxx`, and runs `uncrustify` iteratively until output stabilizes.
* **Check Only (Exit non-zero if unformatted, no file modifications)**:
  ```bash
  CFG=/workspaces/ros2/src/ament/ament_lint/ament_uncrustify/ament_uncrustify/configuration/ament_code_style_0_78.cfg

  # Check C++ files:
  uncrustify -c "$CFG" -l CPP --check $(find . -type f \( -name "*.cpp" -o -name "*.cxx" -o -name "*.hpp" -o -name "*.hxx" \))

  # Check C / header files:
  uncrustify -c "$CFG" -l C --check $(find . -type f \( -name "*.c" -o -name "*.cc" -o -name "*.h" -o -name "*.hh" \))
  ```
* **Reformat In-Place (`--replace --no-backup`)**:
  ```bash
  uncrustify -c "$CFG" -l CPP --replace --no-backup $(find . -type f \( -name "*.cpp" -o -name "*.cxx" -o -name "*.hpp" -o -name "*.hxx" \))
  uncrustify -c "$CFG" -l C --replace --no-backup $(find . -type f \( -name "*.c" -o -name "*.cc" -o -name "*.h" -o -name "*.hh" \))
  ```

---

### B. `clang-format` (Underlying tool for `ament_clang_format`)
* **ROS 2 Config File**: [`src/ament/ament_lint/ament_clang_format/ament_clang_format/configuration/.clang-format`](file:///workspaces/ros2/src/ament/ament_lint/ament_clang_format/ament_clang_format/configuration/.clang-format)
* **Check Only (`--dry-run --Werror` in clang-format 10+, or `-output-replacements-xml`)**:
  ```bash
  CFG=/workspaces/ros2/src/ament/ament_lint/ament_clang_format/ament_clang_format/configuration/.clang-format

  clang-format --style="file:$CFG" --dry-run --Werror $(find . -type f \( -name "*.c" -o -name "*.cc" -o -name "*.cpp" -o -name "*.cxx" -o -name "*.h" -o -name "*.hh" -o -name "*.hpp" -o -name "*.hxx" \))
  ```
  *(Note: For older clang-format versions without `--style=file:<path>`, copy `.clang-format` to the workspace root and pass `-style=file`.)*
* **Reformat In-Place (`-i`)**:
  ```bash
  clang-format --style="file:$CFG" -i $(find . -type f \( -name "*.c" -o -name "*.cc" -o -name "*.cpp" -o -name "*.cxx" -o -name "*.h" -o -name "*.hh" -o -name "*.hpp" -o -name "*.hxx" \))
  ```

---

### C. `clang-tidy` (Underlying tool for `ament_clang_tidy`)
* **Prerequisite**: Generate `compile_commands.json` via CMake (`cmake -B build -DCMAKE_EXPORT_COMPILE_COMMANDS=ON`).
* **Check Only**:
  ```bash
  clang-tidy -p build/<pkg_name> --header-filter=".*" $(find src/<pkg_name> -type f \( -name "*.c" -o -name "*.cc" -o -name "*.cpp" -o -name "*.cxx" \))
  ```
* **Reformat / Auto-Fix In-Place (`-fix` or `-fix-errors`)**:
  ```bash
  clang-tidy -p build/<pkg_name> -fix -fix-errors --header-filter=".*" $(find src/<pkg_name> -type f \( -name "*.c" -o -name "*.cc" -o -name "*.cpp" -o -name "*.cxx" \))
  ```

---

### D. `cppcheck` (Underlying tool for `ament_cppcheck`)
* **How Ament Invokes It**: See [`ament_cppcheck/main.py`](file:///workspaces/ros2/src/ament/ament_lint/ament_cppcheck/ament_cppcheck/main.py#L147-L166).
* **Check Only**:
  ```bash
  cppcheck -f --inline-suppr -q -rp \
    --suppress=internalAstError \
    --suppress=unknownMacro \
    -j $(nproc) \
    -I include \
    --error-exitcode=1 \
    src/ include/ test/
  ```
* **Reformat / Fix**: `cppcheck` is a static analyzer and does **not** modify source files. Issues must be fixed manually or via `clang-tidy -fix`.

---

### E. `cpplint` (Underlying tool for `ament_cpplint`)
* **How Ament Invokes It**: [`ament_cpplint/main.py`](file:///workspaces/ros2/src/ament/ament_lint/ament_cpplint/ament_cpplint/main.py#L120-L139) invokes the vendored [`cpplint.py`](file:///workspaces/ros2/src/ament/ament_lint/ament_cpplint/ament_cpplint/cpplint.py) with ROS 2's custom filters and 100-column line length.
* **Check Only**:
  ```bash
  python3 /workspaces/ros2/src/ament/ament_lint/ament_cpplint/ament_cpplint/cpplint.py \
    --counting=detailed \
    --extensions=c,cc,cpp,cxx \
    --headers=h,hh,hpp,hxx \
    --linelength=100 \
    --filter=-build/c++11,-runtime/references,-whitespace/braces,-whitespace/indent,-whitespace/parens,-whitespace/semicolon \
    $(find . -type f \( -name "*.c" -o -name "*.cc" -o -name "*.cpp" -o -name "*.cxx" -o -name "*.h" -o -name "*.hh" -o -name "*.hpp" -o -name "*.hxx" \))
  ```
  *(Note: `ament_cpplint` also patches `cpplint.GetHeaderGuardCPPVariable` in Python to expect double underscores `__` between directory path components in `#ifndef` header guards.)*
* **Reformat / Fix**: `cpplint` is check-only. Formatting violations reported by `cpplint` can be fixed by running `uncrustify --replace --no-backup` or `clang-format -i`.

---

## 3. Calling Underlying Python Linters Directly

### A. `flake8` (Underlying tool for `ament_flake8`)
* **ROS 2 Config File**: [`src/ament/ament_lint/ament_flake8/ament_flake8/configuration/ament_flake8.ini`](file:///workspaces/ros2/src/ament/ament_lint/ament_flake8/ament_flake8/configuration/ament_flake8.ini) (sets `max-line-length = 99`, `import-order-style = google`, and `extend-ignore = B902,C816,D100..D107,D203,D212,D404,I202`).
* **Check Only**:
  ```bash
  flake8 --config=/workspaces/ros2/src/ament/ament_lint/ament_flake8/ament_flake8/configuration/ament_flake8.ini .
  ```
* **Reformat / Fix**: `flake8` itself is strictly a checker. To automatically reformat Python code to satisfy ROS 2's flake8 rules without Ament:
  ```bash
  # Auto-fix PEP 8 formatting (99 char line length):
  autopep8 --in-place --recursive --max-line-length 99 .
  # Or using ruff:
  ruff check --fix --line-length 99 .
  ```

---

### B. `pydocstyle` (Underlying tool for `ament_pep257`)
* **How Ament Invokes It**: [`ament_pep257/main.py`](file:///workspaces/ros2/src/ament/ament_lint/ament_pep257/ament_pep257/main.py#L27-L39) invokes `pydocstyle` with `--ignore=D100,D101,D102,D103,D104,D105,D106,D107,D203,D212,D404` (the `ament` convention).
* **Check Only**:
  ```bash
  pydocstyle --ignore=D100,D101,D102,D103,D104,D105,D106,D107,D203,D212,D404 .
  ```
* **Reformat / Fix**: `pydocstyle` is check-only. To automatically format Python docstrings in-place:
  ```bash
  docformatter --in-place --recursive --wrap-summaries 99 --wrap-descriptions 99 .
  ```

---

### C. `mypy` (Underlying tool for `ament_mypy`)
* **ROS 2 Config Files**:
  * Default: [`src/ament/ament_lint/ament_mypy/ament_mypy/configuration/ament_mypy.ini`](file:///workspaces/ros2/src/ament/ament_lint/ament_mypy/ament_mypy/configuration/ament_mypy.ini)
  * Strict: [`src/ament/ament_lint/ament_mypy/ament_mypy/configuration/ament_mypy_strict.toml`](file:///workspaces/ros2/src/ament/ament_lint/ament_mypy/ament_mypy/configuration/ament_mypy_strict.toml)
* **Check Only**:
  ```bash
  mypy --config-file /workspaces/ros2/src/ament/ament_lint/ament_mypy/ament_mypy/configuration/ament_mypy.ini \
    --cache-dir /dev/null .
  ```
* **Reformat / Fix**: `mypy` is a static type checker and does not auto-modify code.

---

### D. `pycodestyle` & `pyflakes` (Underlying tools for `ament_pycodestyle` & `ament_pyflakes`)
* **Check Only (`pycodestyle`)**:
  ```bash
  pycodestyle --config=/workspaces/ros2/src/ament/ament_lint/ament_pycodestyle/ament_pycodestyle/configuration/ament_pycodestyle.ini .
  ```
* **Check Only (`pyflakes`)**:
  ```bash
  pyflakes .
  ```
* **Reformat / Fix**:
  * For `pycodestyle`: `autopep8 --in-place --recursive --max-line-length 99 .`
  * For `pyflakes` (unused imports/variables): `autoflake --in-place --remove-all-unused-imports --recursive .`

---

## 4. Calling Underlying XML, CMake, and Copyright Tools Directly

### A. `xmllint` (Underlying tool for `ament_xmllint`)
* **How Ament Invokes It**: [`ament_xmllint/main.py`](file:///workspaces/ros2/src/ament/ament_lint/ament_xmllint/ament_xmllint/main.py#L94-L114) parses each `.xml` file for `<?xml-model href="..." schematypens="..."?>` or `xsi:noNamespaceSchemaLocation` attributes, downloads/caches the XSD/RelaxNG/Schematron schema, and runs `xmllint --noout --schema <xsd> <file>`.
* **Check Only (Well-formedness + XSD schema validation)**:
  ```bash
  # Check XML well-formedness on all XML files:
  xmllint --noout $(find . -name "*.xml")

  # Validate package.xml against ROS package format 3 XSD schema:
  xmllint --noout --schema http://download.ros.org/schema/package_format3.xsd package.xml
  ```
* **Reformat In-Place (`xmllint --format`)**:
  While `ament_xmllint` does not expose `--reformat`, the underlying `xmllint` binary **does** support formatting XML via `--format`:
  ```bash
  for f in $(find . -name "*.xml"); do
    XMLLINT_INDENT="  " xmllint --format "$f" -o "$f"
  done
  ```

---

### B. `cmakelint` (Underlying tool for `ament_lint_cmake`)
* **How Ament Invokes It**: [`ament_lint_cmake/main.py`](file:///workspaces/ros2/src/ament/ament_lint/ament_lint_cmake/ament_lint_cmake/main.py#L74-L93) uses the vendored [`cmakelint.py`](file:///workspaces/ros2/src/ament/ament_lint/ament_lint_cmake/ament_lint_cmake/cmakelint.py) with `--linelength=140`.
* **Check Only**:
  ```bash
  python3 /workspaces/ros2/src/ament/ament_lint/ament_lint_cmake/ament_lint_cmake/cmakelint.py \
    --linelength=140 \
    $(find . -type f \( -name "CMakeLists.txt" -o -name "*.cmake" -o -name "*.cmake.in" \))
  ```
* **Reformat / Fix**: `cmakelint` is check-only. To auto-format `CMakeLists.txt` and `*.cmake` files directly on the CLI, use `cmake-format` (from `cmakelang`):
  ```bash
  cmake-format -i --line-width 140 $(find . -type f \( -name "CMakeLists.txt" -o -name "*.cmake" \))
  ```
*(Note: Be careful with `cmake-format` on ROS 2 packages, as its default indentation style can sometimes conflict with `cmakelint` unless configured with `.cmake-format.py`.)*

---

### C. Copyright & License Headers (`ament_copyright`)
* **Underlying Implementation**: `ament_copyright` does not wrap an external binary; [`ament_copyright/main.py`](file:///workspaces/ros2/src/ament/ament_lint/ament_copyright/ament_copyright/main.py) is the direct Python implementation.
* **Check Only (Direct Python module invocation)**:
  ```bash
  PYTHONPATH=/workspaces/ros2/src/ament/ament_lint/ament_copyright \
    python3 -m ament_copyright.main .
  ```
* **Fix / Add Missing Headers In-Place**:
  ```bash
  PYTHONPATH=/workspaces/ros2/src/ament/ament_lint/ament_copyright \
    python3 -m ament_copyright.main --add-missing "Open Source Robotics Foundation, Inc." apache2 .
  ```
* **Non-Ament Ecosystem Equivalent**: If `ament_copyright` is unavailable altogether, the standard SPDX/FSFE CLI tool [`reuse`](https://reuse.software/) (`reuse lint` to check, `reuse annotate --copyright="..." --license="Apache-2.0" <files>` to fix) or `licenseheaders` serves the same purpose.
