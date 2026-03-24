# ProjectCodeExtractor

`ProjectCodeExtractor` is now a Rust CLI application that flattens a project into one shareable text bundle while respecting `.gitignore` and `excluded_files.txt`.

## What Changed

- Rewritten from a single Python script into a structured Rust application.
- Added a real CLI with file, stdout, and clipboard output modes.
- Replaced ad-hoc ignore matching with `ignore`, so `.gitignore` handling is much closer to real Git behavior.
- Added binary-file detection, deterministic ordering, and automated tests.
- Split responsibilities into focused modules instead of one large script.

## Features

- Recursively walks a project directory.
- Respects `.gitignore` and `excluded_files.txt`.
- Skips hidden files and directories by default.
- Skips binary files automatically.
- Copies the extracted bundle to the system clipboard by default.
- Can also write the bundle to a file or print it to stdout.

## Requirements

- Rust 1.85+ recommended
- Cargo

## Build

```bash
cargo build --release
```

The binary will be available at `target/release/project_code_extractor`.

## Usage

Copy the extracted project bundle to the clipboard:

```bash
cargo run -- /path/to/project
```

Write the bundle to a file:

```bash
cargo run -- /path/to/project --output extracted.txt --no-clipboard
```

Print the bundle to stdout:

```bash
cargo run -- /path/to/project --stdout --no-clipboard
```

Include hidden files and directories:

```bash
cargo run -- /path/to/project --include-hidden
```

Show verbose skip messages:

```bash
cargo run -- /path/to/project --verbose
```

## CLI Options

```text
project-code-extractor [PATH]

Arguments:
  [PATH]                     Project directory to scan. Defaults to the current directory

Options:
  -o, --output <FILE>        Write the extracted bundle to a file
      --stdout               Print the extracted bundle to stdout
      --no-clipboard         Do not copy the bundle to the clipboard
      --include-hidden       Include hidden files and directories
      --excluded-file-name   Additional ignore-file name to load alongside .gitignore
  -v, --verbose              Print non-fatal skip details to stderr
  -h, --help                 Print help
  -V, --version              Print version
```

## Ignore Rules

The extractor reads:

- `.gitignore`
- `excluded_files.txt`

Example `excluded_files.txt`:

```text
*.md
tmp/
coverage/
```

## Development

Format the code:

```bash
cargo fmt
```

Run tests:

```bash
cargo test
```

## Architecture

- `src/cli.rs`: CLI parsing and command-line contract
- `src/extractor.rs`: directory walking, ignore handling, binary detection
- `src/formatter.rs`: stable output rendering
- `src/clipboard.rs`: clipboard integration
- `src/lib.rs`: application orchestration

## License

Distributed under the Apache 2.0 License. See [LICENSE](LICENSE).
