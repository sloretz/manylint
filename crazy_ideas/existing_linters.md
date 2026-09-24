# Existing Linters in ROS 2 / Ament

In ROS 2 / Ament (`src/ament/ament_lint`), each linter is split into two packages:
1. **`ament_<linter>`**: A standalone Python CLI tool and library that runs the linter and outputs JUnit/XUnit XML test results.
2. **`ament_cmake_<linter>`**: CMake macros and [`ament_lint_auto`](file:///workspaces/ros2/src/ament/ament_lint/ament_lint_auto/doc/index.rst) hooks that wrap the CLI tool as a CTest test.

---

## 1. What the Default Linters Are

The standard set of linters is defined by [`ament_lint_common/package.xml`](file:///workspaces/ros2/src/ament/ament_lint/ament_lint_common/package.xml#L25-L32). It includes **8 default linters**:

| CMake Package | CLI / Python Package | Target Files (Globbed in Hook) | Purpose |
| :--- | :--- | :--- | :--- |
| [`ament_cmake_copyright`](file:///workspaces/ros2/src/ament/ament_lint/ament_cmake_copyright/cmake/ament_cmake_copyright_lint_hook.cmake#L15-L23) | `ament_copyright` | All tracked source files | Checks copyright & license headers |
| [`ament_cmake_cppcheck`](file:///workspaces/ros2/src/ament/ament_lint/ament_cmake_cppcheck/cmake/ament_cmake_cppcheck_lint_hook.cmake#L17-L26) | `ament_cppcheck` | `*.c`, `*.cc`, `*.cpp`, `*.cxx`, `*.h`, `*.hh`, `*.hpp`, `*.hxx` | C/C++ static analysis |
| [`ament_cmake_cpplint`](file:///workspaces/ros2/src/ament/ament_lint/ament_cmake_cpplint/cmake/ament_cmake_cpplint_lint_hook.cmake#L15-L24) | `ament_cpplint` | `*.c`, `*.cc`, `*.cpp`, `*.cxx`, `*.h`, `*.hh`, `*.hpp`, `*.hxx` | Google C++ style guide checker |
| [`ament_cmake_uncrustify`](file:///workspaces/ros2/src/ament/ament_lint/ament_cmake_uncrustify/cmake/ament_cmake_uncrustify_lint_hook.cmake#L15-L24) | `ament_uncrustify` | `*.c`, `*.cc`, `*.cpp`, `*.cxx`, `*.h`, `*.hh`, `*.hpp`, `*.hxx` | C/C++ formatting checker |
| [`ament_cmake_flake8`](file:///workspaces/ros2/src/ament/ament_lint/ament_cmake_flake8/cmake/ament_cmake_flake8_lint_hook.cmake#L15-L20) | `ament_flake8` | `*.py` | Python syntax & PEP 8 style checker |
| [`ament_cmake_pep257`](file:///workspaces/ros2/src/ament/ament_lint/ament_cmake_pep257/cmake/ament_cmake_pep257_lint_hook.cmake#L15-L19) | `ament_pep257` | `*.py` | Python docstring conventions (PEP 257) |
| [`ament_cmake_lint_cmake`](file:///workspaces/ros2/src/ament/ament_lint/ament_cmake_lint_cmake/cmake/ament_cmake_lint_cmake_lint_hook.cmake#L15-L18) | `ament_lint_cmake` | `CMakeLists.txt`, `*.cmake` | CMake formatting & style checker |
| [`ament_cmake_xmllint`](file:///workspaces/ros2/src/ament/ament_lint/ament_cmake_xmllint/cmake/ament_cmake_xmllint_lint_hook.cmake#L15-L19) | `ament_xmllint` | `*.xml` (including `package.xml`) | XML syntax & schema (`xmllint`) validator |

### Additional (Non-Default) Linters in `src/ament/ament_lint`
* `ament_cmake_clang_format` / `ament_clang_format` (commented out in `ament_lint_common`)
* `ament_cmake_clang_tidy` / `ament_clang_tidy` (commented out in `ament_lint_common`)
* `ament_cmake_mypy` / `ament_mypy`
* `ament_cmake_pclint` / `ament_pclint`
* `ament_cmake_pycodestyle` / `ament_pycodestyle`
* `ament_cmake_pyflakes` / `ament_pyflakes`

---

## 2. How the Default Linters Are Decided

Default linters are decided through a **3-step discovery and filtering mechanism**:

1. **Manifest Dependency Resolution (`package.xml` + `ament_lint_common`)**:
   * [`ament_lint_auto_find_test_dependencies()`](file:///workspaces/ros2/src/ament/ament_lint/ament_lint_auto/cmake/ament_lint_auto_find_test_dependencies.cmake#L23-L41) parses the `<test_depend>` tags from the package's `package.xml` and runs `find_package(<dep> QUIET)` on each entry.
   * Because [`ament_lint_common/CMakeLists.txt`](file:///workspaces/ros2/src/ament/ament_lint/ament_lint_common/CMakeLists.txt#L8-L9) calls `ament_export_dependencies(${${PROJECT_NAME}_EXEC_DEPENDS})`, depending on `ament_lint_common` automatically calls `find_package()` on all 8 `ament_cmake_*` linters.
2. **Ament Extension Hooks**:
   * When each `ament_cmake_<linter>` package is found, its `*-extras.cmake` file (e.g. [`ament_cmake_uncrustify-extras.cmake`](file:///workspaces/ros2/src/ament/ament_lint/ament_cmake_uncrustify/ament_cmake_uncrustify-extras.cmake#L21-L22)) registers a lint hook under the `"ament_lint_auto"` extension point via `ament_register_extension()`.
   * Meanwhile, [`ament_lint_auto-extras.cmake`](file:///workspaces/ros2/src/ament/ament_lint/ament_lint_auto/ament_lint_auto-extras.cmake#L27-L28) registers [`ament_lint_auto_package_hook.cmake`](file:///workspaces/ros2/src/ament/ament_lint/ament_lint_auto/cmake/ament_lint_auto_package_hook.cmake#L21) to run during `ament_package()`, executing all registered `"ament_lint_auto"` extensions except any listed in `AMENT_LINT_AUTO_EXCLUDE`.
3. **File-Presence Heuristics in Each Hook**:
   * Even if all 8 linters are loaded via `ament_lint_common`, each linter's `*_lint_hook.cmake` uses `file(GLOB_RECURSE ...)` in the package source directory and **only registers a test if matching files exist** (for example, a C++-only package with no `*.py` files will skip `flake8` and `pep257`). `copyright` always runs, and `xmllint` and `lint_cmake` always run in CMake packages because `package.xml` and `CMakeLists.txt` exist.

---

## 3. How Linters Are Invoked

1. **Via CMake / CTest (`ament_cmake` packages)**:
   * Each `*_lint_hook.cmake` calls its corresponding CMake function (e.g., [`ament_uncrustify()`](file:///workspaces/ros2/src/ament/ament_lint/ament_cmake_uncrustify/cmake/ament_uncrustify.cmake#L43-L98)).
   * The CMake function locates the `ament_<linter>` executable via `find_program()`, passes `--xunit-file ${AMENT_TEST_RESULTS_DIR}/${PROJECT_NAME}/<testname>.xunit.xml` (plus any config/exclude flags), and registers it with [`ament_add_test()`](file:///workspaces/ros2/src/ament/ament_lint/ament_cmake_uncrustify/cmake/ament_uncrustify.cmake#L85-L97) and CTest labels `"<linter>;linter"`.
2. **Via Pytest (`ament_python` packages)**:
   * Python test files import the CLI entry point (`main` or `main_with_errors`) from `ament_<linter>.main` and assert that the return code is `0`.
3. **Directly from the Command Line**:
   * Run all linter tests via colcon/CTest:
     ```bash
     colcon test --packages-select <pkg> --ctest-args -L linter
     ```
   * Run a specific linter CLI directly (many support `--reformat` to auto-fix):
     ```bash
     ament_uncrustify --reformat
     ament_clang_format --reformat
     ament_flake8
     ament_xmllint
     ```

---

## 4. How to Include Linters in Tests

### A. In `ament_cmake` Packages (Automatic via `ament_lint_auto`)
See [`rclcpp/package.xml`](file:///workspaces/ros2/src/ros2/rclcpp/rclcpp/package.xml#L54-L55) and [`rclcpp/CMakeLists.txt`](file:///workspaces/ros2/src/ros2/rclcpp/rclcpp/CMakeLists.txt#L266-L273) for a typical example:

1. **`package.xml`**:
   ```xml
   <test_depend>ament_lint_auto</test_depend>
   <test_depend>ament_lint_common</test_depend>
   ```
2. **`CMakeLists.txt`** (must be called **before** `ament_package()`):
   ```cmake
   if(BUILD_TESTING)
     find_package(ament_lint_auto REQUIRED)

     # Optional: exclude specific linter packages
     # list(APPEND AMENT_LINT_AUTO_EXCLUDE ament_cmake_copyright)

     # Optional: exclude specific files/directories across all auto linters
     # list(APPEND AMENT_LINT_AUTO_FILE_EXCLUDE "src/third_party/*")

     ament_lint_auto_find_test_dependencies()
   endif()

   ament_package()
   ```

### B. In `ament_cmake` Packages (Explicit / Custom Configuration)
If you need custom arguments (such as a custom config file or line length), find the package and invoke the CMake macro directly:
```cmake
if(BUILD_TESTING)
  find_package(ament_cmake_uncrustify REQUIRED)
  ament_uncrustify(
    CONFIG_FILE "my_uncrustify.cfg"
    MAX_LINE_LENGTH 100
    EXCLUDE "include/generated/*"
  )
endif()
```

### C. In `ament_python` Packages (Pytest)
Pure Python packages do not run CMake, so `ament_lint_auto` is not used. Instead (as seen in [`rqt_publisher`](file:///workspaces/ros2/src/ros-visualization/rqt_publisher/test/test_flake8.py#L31-L41)):

1. **`package.xml`**:
   ```xml
   <test_depend>ament_copyright</test_depend>
   <test_depend>ament_flake8</test_depend>
   <test_depend>ament_pep257</test_depend>
   <test_depend>ament_xmllint</test_depend>
   <test_depend>python3-pytest</test_depend>
   ```
2. **Add `test/test_<linter>.py` files** (marked with `@pytest.mark.linter`):
   * [`test/test_copyright.py`](file:///workspaces/ros2/src/ros-visualization/rqt_publisher/test/test_copyright.py#L31-L39): Calls `ament_copyright.main.main()`
   * [`test/test_flake8.py`](file:///workspaces/ros2/src/ros-visualization/rqt_publisher/test/test_flake8.py#L31-L42): Calls `ament_flake8.main.main_with_errors(argv=[])`
   * [`test/test_pep257.py`](file:///workspaces/ros2/src/ros-visualization/rqt_publisher/test/test_pep257.py#L31-L40): Calls `ament_pep257.main.main()`
   * [`test/test_xmllint.py`](file:///workspaces/ros2/src/ros-visualization/rqt_publisher/test/test_xmllint.py#L31-L40): Calls `ament_xmllint.main.main(argv=[])`
