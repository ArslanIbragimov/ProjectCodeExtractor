# ProjectCodeExtractor

ProjectCodeExtractor is a Python command-line tool that collects the text files in a project into one document. The result can be copied to the clipboard, written to a file, or printed to stdout, making it useful for code review, documentation, migration, and sharing project context with AI tools.

## Features

- **Accurate `.gitignore` support**: uses gitwildmatch semantics, including nested `.gitignore` files, negation patterns, directory-only patterns, anchored patterns, and `**`.
- **Additional exclusions**: supports `excluded_files.txt`, repeated `--exclude` patterns, and repeated `--exclude-file` files.
- **Flexible output**: copy to the clipboard, write to a file, print to stdout, or combine destinations. Clipboard writes are verified so broken clipboard backends do not fail silently.
- **Text or Markdown output**: Markdown output uses per-file headings, syntax-language hints, and safe code fences.
- **Safe defaults**: skips hidden files, `.git`, binary files, invalid-text files, and symlinks unless explicitly enabled.
- **Useful limits**: optionally skip files larger than a specified size.
- **Installable CLI and Python API**: use the `project-code-extractor` command or import the package.

## Requirements

- Python 3.10 or newer

## Installation

Install directly from GitHub:

```bash
pip install git+https://github.com/ArslanIbragimov/ProjectCodeExtractor.git
```

Or install a local checkout:

```bash
git clone https://github.com/ArslanIbragimov/ProjectCodeExtractor.git
cd ProjectCodeExtractor
pip install .
```

For an isolated CLI installation, `pipx` also works:

```bash
pipx install git+https://github.com/ArslanIbragimov/ProjectCodeExtractor.git
```

## Usage

Extract the current project and copy the result to the clipboard:

```bash
project-code-extractor
```

Extract a specific project:

```bash
project-code-extractor /path/to/project
```

Write the result to a file instead of copying it:

```bash
project-code-extractor /path/to/project --output project.txt
```

Print to stdout:

```bash
project-code-extractor /path/to/project --stdout
```

Write Markdown, including syntax-highlighted code fences:

```bash
project-code-extractor . --format markdown --output project.md
```

Copy to the clipboard in addition to another destination:

```bash
project-code-extractor . --output project.txt --clipboard
```

After installing the package or its dependencies, the legacy entry point still works from a source checkout and accepts the same arguments:

```bash
python projcode.py . --stdout
```

### CLI options

| Option | Description |
| --- | --- |
| `project_path` | Project directory to extract. Defaults to the current directory. |
| `-o`, `--output FILE` | Write rendered output to `FILE`. If the file is inside the project, it is excluded from extraction. |
| `--stdout` | Write rendered output to stdout. |
| `--clipboard` | Copy to the clipboard even when `--output` or `--stdout` is used. |
| `--format text\|markdown` | Select output format. Default: `text`. |
| `--include-hidden` | Include hidden files and directories. `.git` is always excluded. |
| `--exclude PATTERN` | Add one gitignore-style exclusion pattern. Can be repeated. |
| `--exclude-file FILE` | Read additional gitignore-style patterns from `FILE`. Can be repeated. |
| `--encoding ENCODING` | Encoding used to read text files. Default: `utf-8`. |
| `--max-file-size SIZE` | Skip files larger than `SIZE`, for example `500KB`, `2MiB`, or `1000000`. |
| `--follow-symlinks` | Follow symlinked files and directories. Symlinks are skipped by default; directory cycles are detected. |
| `-v`, `--verbose` | Print each skipped file and its reason to stderr. |
| `--quiet` | Suppress the extraction summary printed to stderr. |
| `--version` | Print the installed version. |

If neither `--output` nor `--stdout` is given, the clipboard is the default destination. Be careful with `--include-hidden`: hidden files such as `.env` often contain credentials.

## Exclusion rules

ProjectCodeExtractor reads:

1. The root `.gitignore` and nested `.gitignore` files.
2. `excluded_files.txt` in the project root.
3. Patterns passed with `--exclude-file` and `--exclude`.

`.gitignore` files follow Git's pattern rules, including nested overrides and negation:

```gitignore
# Ignore all log files
*.log

# Ignore build directories
build/

# Ignore only the root config file
/config.local.json

# Re-include one otherwise ignored file
!important.log
```

`excluded_files.txt` uses the same gitignore-style syntax. The root `excluded_files.txt` is treated as extractor configuration and is never included in the output; files passed with `--exclude-file` are also excluded when they are inside the project. Custom exclusion rules from `excluded_files.txt`, `--exclude-file`, and `--exclude` are evaluated after `.gitignore` rules, so they take precedence when both match the same file.

Additional examples:

```bash
# Exclude lock files and generated output
project-code-extractor . --exclude '*.lock' --exclude 'generated/'

# Load extra patterns from a file outside the project
project-code-extractor . --exclude-file ~/shared-exclusions.txt
```

Files skipped because of ignore rules, binary content, size limits, encoding errors, or symlink handling are counted in the final summary. Directories excluded by ignore rules are not traversed.

## Output formats

### Text

The default format preserves the original separator-oriented output:

```text
————
————————————
src/app.py:

print("hello")
————————————
————
```

### Markdown

Markdown output is convenient for documentation, review tools, and AI prompts:

````markdown
## `src/app.py`

```python
print("hello")
```
````

The code fence length is increased automatically when a file itself contains triple backticks.

## Python API

```python
from project_code_extractor import ProjectCodeExtractor

extractor = ProjectCodeExtractor(
    "/path/to/project",
    output_format="markdown",
    max_file_size=500_000,
)
result = extractor.extract_code()

print(result.content)
print([file.path for file in result.files])
print([(file.path, file.reason) for file in result.skipped_files])
```

## Development

Create a virtual environment and install the package in editable mode:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

Run tests:

```bash
pytest
```

Run lint and formatting checks:

```bash
ruff check src tests projcode.py
ruff format --check src tests projcode.py
```

Build the package:

```bash
python -m build
```

## Contributing

Issues and pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License

Distributed under the Apache 2.0 License. See [LICENSE](LICENSE) for more information.
