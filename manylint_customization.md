# Customizing `manylint` per Package via `package.xml` (`<export><manylint>`)

`manylint` reads per-package configuration from `<export><manylint>` in `package.xml`.
To keep configuration simple and avoid reinventing linter settings in XML, **`manylint` delegates rule customization to each linter's native configuration file format** whenever possible, using a minimal, uniform set of XML tags.

---

## 1. Uniform XML Schema

Every linter tag inside `<export><manylint>` shares the same minimal structure:
* **`enabled="true|false"`** *(attribute)*: Enable or disable the linter for this package.
* **`<config>path/to/file</config>`**: Path to the linter's native config file (relative to `package.xml`).
* **`<exclude>glob/pattern</exclude>`**: File or directory glob to exclude (can be specified at the `<manylint>` level for all linters, or inside a specific `<linter>` tag).
* **`<args>...</args>`**: Raw command-line arguments (parsed with `shlex.split()`) passed directly to the linter for tools that do not use a config file or need extra CLI flags.

```xml
<export>
  <build_type>ament_cmake</build_type>
  <manylint default_linters="true">
    <!-- Package-wide file exclusions across all linters -->
    <exclude>src/third_party/**</exclude>

    <!-- Disable a default linter -->
    <uncrustify enabled="false"/>

    <!-- Enable an optional linter and point to its native .clang-format file -->
    <clang_format>
      <config>.clang-format</config>
    </clang_format>

    <!-- Pass CLI flags to a linter without a config file -->
    <cppcheck>
      <exclude>test/benchmark_*.cpp</exclude>
      <args>-I include --language=c++</args>
    </cppcheck>
  </manylint>
</export>
```

* If `default_linters="false"` is set on `<manylint>`, **only** the linters explicitly listed inside `<manylint>` are run.
* If `default_linters="true"` (the default), the standard `ament_lint_common` linters run unless disabled with `enabled="false"`.

---

## 2. XML Tags Reference for Each Linter

### A. Linters Configured via Native Config Files (`<config>`)

| XML Tag | Native Config File Format (`<config>`) | Example `<export><manylint>` Entry |
| :--- | :--- | :--- |
| **`<uncrustify>`** | Uncrustify `.cfg` file | `<uncrustify><config>uncrustify.cfg</config></uncrustify>` |
| **`<clang_format>`** | `.clang-format` YAML file | `<clang_format><config>.clang-format</config></clang_format>` |
| **`<clang_tidy>`** | `.clang-tidy` YAML file | `<clang_tidy><config>.clang-tidy</config></clang_tidy>` |
| **`<flake8>`** | INI file (`[flake8]` in `.flake8` or `setup.cfg`) | `<flake8><config>.flake8</config></flake8>` |
| **`<pep257>`** | INI file (`[pydocstyle]` in `.pydocstyle` or `setup.cfg`) | `<pep257><config>.pydocstyle</config></pep257>` |
| **`<pycodestyle>`** | INI file (`[pycodestyle]` in `setup.cfg` or `.pycodestyle`) | `<pycodestyle><config>setup.cfg</config></pycodestyle>` |
| **`<mypy>`** | `mypy.ini`, `.mypy.ini`, or `pyproject.toml` | `<mypy><config>mypy.ini</config></mypy>` |
| **`<lint_cmake>`** | `.cmakelintrc` file | `<lint_cmake><config>.cmakelintrc</config></lint_cmake>` |
| **`<pclint>`** | PC-lint `.lnt` file | `<pclint><config>config/custom.lnt</config></pclint>` |

*(Note: `cpplint` also automatically reads `CPPLINT.cfg` files placed in the package directory or subdirectories.)*

### B. Linters Configured via `<exclude>` and `<args>`

For linters that do not use a standalone config file (or when passing simple CLI flags is easier than creating a file):

* **`<cpplint>`** (uses `CPPLINT.cfg` if present in directory, or `<args>`):
  ```xml
  <cpplint>
    <exclude>include/generated/**</exclude>
    <args>--linelength=120 --filter=-whitespace/braces,-readability/todo</args>
  </cpplint>
  ```
* **`<cppcheck>`**:
  ```xml
  <cppcheck>
    <exclude>src/experimental/**</exclude>
    <args>-I include --language=c++ --suppress=knownConditionTrueFalse</args>
  </cppcheck>
  ```
* **`<copyright>`**:
  ```xml
  <copyright>
    <exclude>src/external/**</exclude>
    <args>--add-missing "Open Source Robotics Foundation, Inc." apache2</args>
  </copyright>
  ```
* **`<xmllint>`** (schemas are already declared inside each XML file via `<?xml-model?>`):
  ```xml
  <xmllint>
    <exclude>test/malformed_fixtures/*.xml</exclude>
    <args>--extensions xml launch urdf xacro</args>
  </xmllint>
  ```
* **`<pyflakes>`**:
  ```xml
  <pyflakes>
    <exclude>test/legacy_*.py</exclude>
  </pyflakes>
  ```

---

## 3. How Custom Arguments Are Parsed

1. **Path Resolution**:
   * Relative paths in `<config>` and `<exclude>` are resolved relative to the package directory containing `package.xml`.
2. **`<config>` Forwarding**:
   * Passed directly to the linter's native config flag (`-c <path>` for `uncrustify`, `--config <path>` for `flake8`, `pep257`, `pycodestyle`, `mypy`, `lint_cmake`, `clang_format`, `clang_tidy`, and `--pclint-config-file <path>` for `pclint`).
3. **`<args>` Tokenization**:
   * The text inside `<args>...</args>` is split using POSIX shell rules via Python's `shlex.split()` (so quoted strings like `"Open Source Robotics Foundation, Inc."` remain a single argument) and appended to the linter command.

---

## 4. Warning on Unsupported Linters

When `manylint` parses `<export><manylint>`, it checks every child XML tag against the list of supported linters (`clang_format`, `clang_tidy`, `copyright`, `cppcheck`, `cpplint`, `flake8`, `lint_cmake`, `mypy`, `pclint`, `pep257`, `pycodestyle`, `pyflakes`, `uncrustify`, `xmllint`) and `<exclude>`.

If a package specifies an unknown or unsupported linter tag (e.g., `<rustfmt/>` or a typo like `<uncrustfiy/>`):
1. **Prints a warning to `stderr`** with the package name, `package.xml` path and line number, the unknown tag name, and a typo suggestion if applicable:
   ```text
   WARNING [manylint]: my_pkg (src/my_pkg/package.xml:24): Unsupported linter '<rustfmt>' in <export><manylint>; skipping.
   WARNING [manylint]: my_pkg (src/my_pkg/package.xml:25): Unsupported linter '<uncrustfiy>' in <export><manylint>; skipping. Did you mean '<uncrustify>'?
   ```
2. **Skips the unknown tag and continues running** all valid linters for the package so a single unrecognized tag does not break linting across the workspace.
