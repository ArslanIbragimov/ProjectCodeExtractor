# ProjectCodeExtractor

## Overview

`ProjectCodeExtractor` is a Python script that recursively copies the contents of all files in a specified project directory, while ignoring files and directories specified in `.gitignore` and `excluded_files.txt`. The extracted content is then copied to the clipboard for easy access and sharing.

## Features

- **Recursive Extraction**: Recursively walks through the project directory to extract code from all files.
- **Exclusion Support**: Supports exclusion patterns from `.gitignore` and `excluded_files.txt`.
- **Hidden Files/Directories Ignored**: Automatically ignores hidden files and directories.
- **Clipboard Integration**: Copies the formatted content directly to the clipboard using `pyperclip`.

## Requirements

- Python 3.6+
- `pyperclip` library

Install the required library using pip:

```bash
pip install pyperclip
```

## Usage
### Clone the Repository:
git clone https://github.com/yourusername/ProjectCodeExtractor.git

cd ProjectCodeExtractor

### Prepare Your Project Directory:
Ensure you have .gitignore and excluded_files.txt in your project directory with appropriate patterns to exclude files and directories.

### Run the Script:
python projcode.py

You will be prompted to enter the path to your project directory.

### Check the Clipboard:
  
The script will copy the extracted code content to your clipboard, which you can then paste wherever needed.

## Exclusion Patterns

- **.gitignore: This file should contain patterns for files and directories you want to exclude from extraction.**
- **excluded_files.txt: This file should also contain patterns for files and directories to be excluded. Both files follow the same pattern matching rules as .gitignore.**

Example file:

```
# Ignore all log files
*.log
```

```
# Ignore node_modules directory
node_modules/
Example excluded_files.txt
```

```
# Ignore all markdown files
*.md
```

```
# Ignore temp directory
temp/
```

## Useful Tips and Applications
### Code Review: **Quickly gather all code for a review session and share it via clipboard.**
### Documentation: **Easily extract code snippets to include in your documentation.**
### Backup: **Extract and store important code segments without version control.**
### Migration: **Prepare code segments for migrating to a new project or repository.**
### Generative AI Tools: **Use this script to gather code snippets for training or querying generative neural networks.**
### Stack Overflow Questions: **Simplify the process of collecting and sharing relevant code snippets when asking or answering questions on Stack Overflow.**

Contributing
Feel free to submit issues and pull requests. For major changes, please open an issue first to discuss what you would like to change.

License
Distributed under the Apache 2.0 License. See LICENSE for more information.

By following the above instructions and utilizing the provided features, you can make the most out of the ProjectCodeExtractor script. Happy coding!
