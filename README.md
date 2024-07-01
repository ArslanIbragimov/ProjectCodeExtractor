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

Here’s a snippet of how the ProjectCodeExtractor works:


```python
import os
import pyperclip
from fnmatch import fnmatch

class ProjectCodeExtractor:
    def __init__(self, project_path):
        self.project_path = project_path
        self.output = []
        self.excluded_patterns = self.load_exclusions('.gitignore') + self.load_exclusions('excluded_files.txt')

    def load_exclusions(self, filename):
        file_path = os.path.join(self.project_path, filename)
        if not os.path.exists(file_path):
            return []

        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            patterns = f.read().splitlines()
        return [pattern.strip() for pattern in patterns if pattern.strip() and not pattern.startswith('#')]

    def is_excluded(self, path):
        rel_path = os.path.relpath(path, self.project_path)
        for pattern in self.excluded_patterns:
            if fnmatch(rel_path, pattern) or fnmatch(os.path.basename(rel_path), pattern):
                return True
        return False

    def extract_code(self):
        for root, dirs, files in os.walk(self.project_path):
            relative_root = os.path.relpath(root, self.project_path)
            if self.is_excluded(relative_root):
                dirs[:] = []
                continue

            dirs[:] = [d for d in dirs if not d.startswith('.')]
            files = [f for f in files if not f.startswith('.')]

            for file in files:
                relative_file = os.path.relpath(os.path.join(root, file), self.project_path)
                if not self.is_excluded(relative_file):
                    file_path = os.path.join(root, file)
                    try:
                        self.output.append(self.format_file_content(file_path))
                    except (PermissionError, UnicodeDecodeError) as e:
                        print(f"Failed to read file {file_path}: {e}")

    def format_file_content(self, file_path):
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        file_name = os.path.relpath(file_path, self.project_path)
        formatted_content = f'————————————\n{file_name}:\n\n{content}\n————————————\n'
        return formatted_content

    def save_to_clipboard(self):
        pyperclip.copy('————\n' + '\n'.join(self.output) + '————')
        print("Code extracted and copied to clipboard!")

    def run(self):
        self.extract_code()
        self.save_to_clipboard()

if __name__ == "__main__":
    project_path = input("Enter the path to your project directory: ")
    extractor = ProjectCodeExtractor(project_path)
    extractor.run()
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
