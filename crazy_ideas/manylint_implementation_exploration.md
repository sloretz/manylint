# `manylint` Implementation Exploration: Zero-Dependency Static Binary Architecture

## 1. The Core Engineering Goal

Even inside a standard ROS 2 developer environment, system-installed linter binaries and Python packages drift across OS versions (for example, Ubuntu 22.04 vs. 24.04 ships different versions of `uncrustify`, `cppcheck`, and `python3-flake8`, producing different lint results on the same code).

To guarantee that **`manylint` lints and formats identically on every machine (`linux-amd64`, `linux-arm64`, `osx-arm64`, `osx-amd64`, `windows-amd64`) with zero system dependencies**, the `manylint` executable must internally embed:
1. **Exact pinned versions of every linter engine** (C/C++ tools and Python tools + plugins).
2. **Exact pinned versions of all ROS 2 default configuration files** (`ament_code_style_0_78.cfg`, `ament_flake8.ini`, `.clang-format`, XSD schemas `package_format2.xsd` / `package_format3.xsd`).

We prototyped and verified static linking in `/opt/jetski/.gemini/jetski/brain/0910ada6-84b5-4e4c-bde8-e383a460da01/scratch/proto_static.cpp` (`g++ -static -O2`), confirming `ldd` reports `not a dynamic executable` and that C/C++ linters (`uncrustify`, `cppcheck`) can have their entry points compiled as static libraries (`-Dmain=uncrustify_main`) and invoked in-process.

---

## 2. Inventory of What Must Be Bundled

| Linter | Implementation Language | Dependencies in `ament_lint` | How to Bundle Statically |
| :--- | :--- | :--- | :--- |
| **`uncrustify`** | C++17 | None (pure C++ standard library) | Compile from source as static `cc_library` (`libuncrustify.a`) |
| **`cppcheck`** | C++17 | Bundled `simplecpp`, `tinyxml2`, `picojson` | Compile from source as static `cc_library` (`libcppcheck.a`) |
| **`xmllint`** | C (`libxml2`) | `libxml2` (XML + XSD schema validator) | Compile `libxml2` statically (`libxml2.a`) + embed `package_format2/3.xsd` |
| **`clang_format`** | C++17 (`LLVM`) | `libclangFormat`, `libclangToolingInclusions` | Link `libclangFormat.a` or embed static `clang-format` binary |
| **`cpplint`** | Python (1 file) | [`cpplint.py`](file:///workspaces/ros2/src/ament/ament_lint/ament_cpplint/ament_cpplint/cpplint.py) (stdlib only) | Run on embedded Python runtime (or port rules to C++/Rust) |
| **`lint_cmake`** | Python (1 file) | [`cmakelint.py`](file:///workspaces/ros2/src/ament/ament_lint/ament_lint_cmake/ament_lint_cmake/cmakelint.py) (stdlib only) | Run on embedded Python runtime (or native C++/Rust port) |
| **`copyright`** | Python | [`ament_copyright`](file:///workspaces/ros2/src/ament/ament_lint/ament_copyright/ament_copyright/main.py) (stdlib only) | Run on embedded Python runtime (or native C++/Rust port) |
| **`flake8`** | Python + 7 plugins | `flake8`, `pycodestyle`, `pyflakes`, `mccabe`, `flake8-blind-except`, `flake8-builtins`, `flake8-class-newline`, `flake8-comprehensions`, `flake8-deprecated`, `flake8-import-order`, `flake8-quotes` | Bundle wheels in embedded Python runtime **OR** replace with static Rust **`ruff`** |
| **`pep257`** | Python | `pydocstyle`, `snowballstemmer` | Bundle wheel in embedded Python runtime **OR** replace with static Rust **`ruff`** |

---

## 3. Build System & Host Language Choice

### A. Why Bazel (`Bzlmod` / `MODULE.bazel`)?
Bazel is uniquely suited for building `manylint` because it natively handles:
1. **Hermetic Multi-Language Fetching**: Can fetch and pin C/C++ source tarballs (`http_archive`), Python wheels (`rules_python`), and Rust crates (`rules_rust`) by SHA-256 hash in a single build graph.
2. **Hermetic Static Cross-Compilation**: Using `hermetic_cc_toolchain` (`zig cc`) or `toolchains_llvm`, Bazel can compile C/C++ and Rust targets against `musl` libc on Linux (`-static`), producing a 100% static binary (`not a dynamic executable`) for both `linux-amd64` and `linux-arm64` from a single CI runner.
3. **Embedded Data (`cc_embed_data` / `include_bytes!`)**: Bazel rules can package Python wheels, `.cfg`/`.ini` files, and `.xsd` schemas into a deterministic archive and compile that archive directly into the `.rodata` section of the final executable.

### B. Host Language Comparison: C++ vs. Rust vs. Go

| Criterion | **Rust (`rules_rust`)** | **C++ (`rules_cc`)** | **Go (`rules_go`)** |
| :--- | :--- | :--- | :--- |
| **Static Linking of C/C++ Linters (`uncrustify`, `cppcheck`, `libxml2`)** | Excellent (via `cc` crate or Bazel `deps = [":libuncrustify"]`) | **Native** (direct C/C++ function calls, zero FFI wrapper needed) | Difficult (`cgo` slows builds and complicates static linking) |
| **Native Python Linting (`ruff` crate)** | **Native** (`ruff` is written in Rust and can be linked directly!) | Can link Rust `libruff.a` via C ABI or embed `libpython.a` | Must shell out to extracted binary |
| **CLI, XML/JUnit, Git & Parallelism** | Excellent (`clap`, `ignore`, `rayon`, `quick-xml`, `include_bytes!`) | Good (`CLI11`/`argparse`, `tinyxml2`/`pugixml`, `std::thread`) | Excellent (`cobra`, `//go:embed`, goroutines) |
| **ROS 2 Maintainer Familiarity** | Growing in ROS 2 | **Highest** (primary language of ROS 2 core) | Low in ROS 2 ecosystem |

**Recommendation**: Use **Bazel** as the build system, with either **C++** or **Rust** as the top-level binary language. Even if the top-level CLI is C++, Bazel allows linking C/C++ static libraries (`libuncrustify.a`, `libcppcheck.a`, `libxml2.a`, `libpython3.12.a`) and Rust static libraries (`libruff.a`) into the same static executable.

---

## 4. How to Bundle Linters Written in Different Languages

### A. C and C++ Linters (`uncrustify`, `cppcheck`, `libxml2`) — In-Process Static Libraries
Instead of compiling `uncrustify` and `cppcheck` as separate executables, we compile their source files in Bazel as `cc_library` targets and rename their `main()` symbol using compiler defines (`copts = ["-Dmain=uncrustify_cli_main"]`):

```cpp
// Inside manylint's C++ / Rust runner:
extern "C" int uncrustify_cli_main(int argc, char** argv);
extern "C" int cppcheck_cli_main(int argc, char** argv);
```

* **State Isolation via In-Memory `fork()` (POSIX)**: Because CLI tools like `uncrustify` and `cpplint` use global/static C++ variables across runs, `manylint` can `fork()` a lightweight worker process in memory (without `exec()`, so zero disk files are needed!) to invoke `uncrustify_cli_main(argc, argv)`, capture `stdout`/`stderr` over a pipe, and return the result.
* **`xmllint` In-Process via `libxml2` C API**: Rather than shelling out to `xmllint` and downloading `package_format3.xsd` over HTTP on every run, `manylint` embeds `package_format2.xsd` and `package_format3.xsd` in memory and calls `xmlSchemaNewMemParserCtxt()` + `xmlSchemaValidateDoc()` (for `manylint check`) and `xmlSaveFormatFileEnc()` (for `manylint fix`) directly via `libxml2.a`.

---

### B. Python Linters (`flake8` + 7 Plugins, `pep257`, `cpplint`, `lint_cmake`, `copyright`)

There are **two ways** to bundle the Python linters with zero system dependencies:

#### Strategy 1: Embedded Hermetic CPython + In-Memory Wheel Bundle (100% `ament_lint` Parity)
Why is `flake8` tricky to bundle? Because [`ament_flake8/package.xml`](file:///workspaces/ros2/src/ament/ament_lint/ament_flake8/package.xml#L21-L28) requires **7 external Flake8 plugins**:
* `flake8-blind-except`
* `flake8-builtins`
* `flake8-class-newline`
* `flake8-comprehensions`
* `flake8-deprecated`
* `flake8-import-order` (configured with `import-order-style = google`)
* `flake8-quotes`

Flake8 discovers these plugins at runtime using `importlib.metadata.entry_points(group='flake8.extension')`, which inspects `.dist-info/entry_points.txt` directories.

**How we bundle them into the static binary:**
1. **Static `libpython3.12.a`**: Fetch the prebuilt static Python library from `indygreg/python-build-standalone` (or compile via Bazel).
2. **Pure-Python Wheel Zip (`python_bundle.zip`)**: Every single Python linter and plugin (`flake8`, `pycodestyle`, `pyflakes`, `mccabe`, all 7 `flake8-*` plugins, `pydocstyle`, `snowballstemmer`, `cpplint.py`, `cmakelint.py`, `ament_copyright`) is **100% pure Python** (zero C-extension `.so` files!).
3. **Embed `python_bundle.zip` in `.rodata`**: At build time, a Bazel rule unpacks the Python 3.12 stdlib and all pinned `.whl` files (preserving `.dist-info/entry_points.txt` so `importlib.metadata` discovers all 7 Flake8 plugins!) into a single uncompressed/deflated `python_bundle.zip` and embeds it into the binary.
4. **Execute via `PyConfig` (or Bazel-style `~/.cache/manylint/<sha256>` extraction)**:
   * On startup, `manylint` initializes `libpython3.12.a` with `PyConfig.module_search_paths` pointing to the embedded `python_bundle.zip` (via an anonymous Linux `memfd_create` file descriptor `/proc/self/fd/<N>` or a one-time content-addressed directory `~/.cache/manylint/<sha256>/`).
   * `PyConfig.isolated = 1` and `PyConfig.use_environment = 0` ensure **host `PYTHONPATH`, `~/.local/lib/python3.*`, and system Python packages are completely ignored**.

#### Strategy 2: Replace Python Linters with Embedded `ruff` (High-Performance Alternative)
We should also consider **`ruff`** (written in Rust):
* `ruff` is a single static Rust library/binary that natively implements almost the entire `ament_flake8` + `ament_pep257` rule set in compiled Rust:
  * `pycodestyle` (`E`, `W`), `pyflakes` (`F`), `flake8-blind-except` (`BLE`), `flake8-builtins` (`A`), `flake8-comprehensions` (`C4`), `flake8-quotes` (`Q`), `isort` (`I`), and `pydocstyle` / `pep257` (`D100`–`D419`).
* **Advantages of `ruff`**:
  1. **50–100x faster** than Python `flake8` + `pydocstyle`.
  2. **Supports `manylint fix` (`ruff check --fix` and `ruff format`)**: Unlike `flake8` and `pydocstyle` (which are check-only), `ruff` can automatically fix Python imports, quotes, comprehensions, docstrings, and PEP 8 formatting!
* **Hybrid Approach**: Embed **both** `ruff` (for fast Python auto-fixing in `manylint fix`) and the hermetic `flake8` + `pydocstyle` bundle (or use `ruff` for both if minor rule differences like `flake8-class-newline` are implemented as a tiny AST check).

---

## 5. How to Write Bazel Repository Rules to Fetch All Linters

In Bazel (`MODULE.bazel`), external linters and configs are fetched and pinned by SHA-256 so every developer and CI build uses the exact same source code:

```python
# MODULE.bazel
module(name = "manylint", version = "0.1.0")

bazel_dep(name = "rules_cc", version = "0.0.10")
bazel_dep(name = "rules_python", version = "0.36.0")
bazel_dep(name = "rules_rust", version = "0.52.0")
bazel_dep(name = "hermetic_cc_toolchain", version = "3.1.0") # Zig CC for static musl builds

http_archive = use_repo_rule("@bazel_tools//tools/build_defs/repo:http.bzl", "http_archive")

# 1. Fetch Uncrustify 0.78.1 (matches ament_code_style_0_78.cfg)
http_archive(
    name = "uncrustify",
    urls = ["https://github.com/uncrustify/uncrustify/archive/refs/tags/uncrustify-0.78.1.tar.gz"],
    strip_prefix = "uncrustify-uncrustify-0.78.1",
    sha256 = "<PINNED_SHA256>",
    build_file = "//third_party/uncrustify:uncrustify.BUILD.bazel",
)

# 2. Fetch Cppcheck 2.14.0
http_archive(
    name = "cppcheck",
    urls = ["https://github.com/danmar/cppcheck/archive/refs/tags/2.14.0.tar.gz"],
    strip_prefix = "cppcheck-2.14.0",
    sha256 = "<PINNED_SHA256>",
    build_file = "//third_party/cppcheck:cppcheck.BUILD.bazel",
)

# 3. Fetch libxml2 (for xmllint validation + --format)
http_archive(
    name = "libxml2",
    urls = ["https://download.gnome.org/sources/libxml2/2.12/libxml2-2.12.7.tar.xz"],
    strip_prefix = "libxml2-2.12.7",
    sha256 = "<PINNED_SHA256>",
    build_file = "//third_party/libxml2:libxml2.BUILD.bazel",
)

# 4. Fetch ament_lint (for cpplint.py, cmakelint.py, ament_copyright, and default configs)
http_archive(
    name = "ament_lint",
    urls = ["https://github.com/ament/ament_lint/archive/refs/tags/0.21.2.tar.gz"],
    strip_prefix = "ament_lint-0.21.2",
    sha256 = "<PINNED_SHA256>",
    build_file = "//third_party/ament_lint:ament_lint.BUILD.bazel",
)

# 5. Fetch Pinned Python Wheels (flake8 + 7 plugins + pydocstyle)
pip = use_extension("@rules_python//python/extensions:pip.bzl", "pip")
pip.parse(
    hub_name = "manylint_pip",
    python_version = "3.12",
    requirements_lock = "//third_party/python:requirements_lock.txt",
)
use_repo(pip, "manylint_pip")
```

And in `third_party/uncrustify/uncrustify.BUILD.bazel`, we expose `uncrustify` as a linkable `cc_library`:

```python
# third_party/uncrustify/uncrustify.BUILD.bazel
cc_library(
    name = "libuncrustify",
    srcs = glob(["src/*.cpp"]),
    hdrs = glob(["src/*.h"]) + [":generated_config_h"],
    copts = [
        "-std=c++17",
        "-Dmain=uncrustify_cli_main", # Rename main() so manylint can link & call it directly
    ],
    visibility = ["//visibility:public"],
)
```

---

## 6. Keeping the Codebase Organized by Linter

To prevent `manylint` from becoming a monolithic tangle of tool-specific flags, the repository is organized with a **strict per-linter module directory** implementing a single `Linter` interface:

```text
manylint/
├── MODULE.bazel
├── src/
│   ├── main.cc                       # CLI parser (`check`, `fix`, `list`)
│   ├── core/
│   │   ├── discovery.{h,cc}          # Finds package.xml & parses <export><manylint>
│   │   ├── git_filter.{h,cc}         # Implements --git-diff and --git-staged
│   │   ├── linter_interface.h        # Abstract Linter class + Violation / Result structs
│   │   ├── registry.{h,cc}           # Registers all linters & warns on unknown XML tags
│   │   └── reporter_{text,junit}.cc  # Formats --output=text and --output=junit
│   ├── runtime/
│   │   └── embedded_python.{h,cc}    # Initializes static libpython + embedded wheel zip
│   └── linters/                      # One self-contained directory per linter!
│       ├── uncrustify/
│       │   ├── BUILD.bazel           # Depends on @uncrustify//:libuncrustify + config
│       │   └── uncrustify_linter.cc
│       ├── cppcheck/
│       │   ├── BUILD.bazel           # Depends on @cppcheck//:libcppcheck
│       │   └── cppcheck_linter.cc
│       ├── cpplint/
│       │   ├── BUILD.bazel           # Embeds @ament_lint//ament_cpplint:cpplint.py
│       │   └── cpplint_linter.cc
│       ├── flake8/
│       │   ├── BUILD.bazel           # Embeds @ament_lint//:ament_flake8.ini + wheels
│       │   └── flake8_linter.cc
│       ├── pep257/
│       │   ├── BUILD.bazel
│       │   └── pep257_linter.cc
│       ├── lint_cmake/
│       │   ├── BUILD.bazel
│       │   └── lint_cmake_linter.cc
│       ├── xmllint/
│       │   ├── BUILD.bazel           # Depends on @libxml2//:libxml2 + embedded XSDs
│       │   └── xmllint_linter.cc
│       └── copyright/
│           ├── BUILD.bazel           # Embeds @ament_lint//ament_copyright
│           └── copyright_linter.cc
└── third_party/
    ├── uncrustify/
    ├── cppcheck/
    ├── libxml2/
    ├── ament_lint/
    └── python/
        └── requirements_lock.txt
```

### The Uniform `Linter` Interface (`src/core/linter_interface.h`)
Every folder under `src/linters/<name>/` implements a single C++ (or Rust) trait:

```cpp
struct Violation {
  std::string file;
  int line = 0;
  int column = 0;
  std::string rule_id;
  std::string message;
  std::string diff; // Populated by formatters (uncrustify, clang_format, xmllint)
};

struct LinterResult {
  std::string package_name;
  std::string linter_name;
  std::vector<std::string> checked_files;
  std::vector<Violation> violations;
  double elapsed_seconds = 0.0;
};

class Linter {
 public:
  virtual ~Linter() = default;
  virtual std::string name() const = 0;
  virtual bool is_default() const = 0;
  virtual bool supports_fix() const = 0;
  virtual std::vector<std::string> matching_extensions() const = 0;

  virtual LinterResult check(
      const PackageContext& pkg,
      const LinterConfig& xml_config,
      const std::vector<std::filesystem::path>& files) = 0;

  virtual LinterResult fix(
      const PackageContext& pkg,
      const LinterConfig& xml_config,
      const std::vector<std::filesystem::path>& files) = 0;
};
```

Because each linter is isolated in its own `src/linters/<name>/` directory with its own `BUILD.bazel`, adding or updating a linter never touches the core package discovery, `<export><manylint>` XML parser, or JUnit/Text reporters.
