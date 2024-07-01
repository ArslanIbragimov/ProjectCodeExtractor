import os
import pyperclip
from fnmatch import fnmatch

class ProjectCodeExtractor:
    def __init__(self, project_path):
        self.project_path = project_path
        self.output = []
        self.excluded_patterns = self.load_exclusions('.gitignore') + self.load_exclusions('excluded_files.txt')
        print(f"Excluded patterns: {self.excluded_patterns}")

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
                print(f"Excluding {rel_path} due to pattern {pattern}")
                return True
        return False

    def extract_code(self):
        for root, dirs, files in os.walk(self.project_path):
            relative_root = os.path.relpath(root, self.project_path)
            if self.is_excluded(relative_root):
                dirs[:] = []
                continue

            dirs[:] = [d for d in dirs if not d.startswith('.')]  # Exclude hidden directories
            files = [f for f in files if not f.startswith('.')]  # Exclude hidden files

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