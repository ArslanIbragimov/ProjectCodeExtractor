"""Core extraction logic for Project Code Extractor."""

import codecs
import os
import re
import warnings
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pyperclip
from pathspec import GitIgnoreSpec
from pathspec.patterns.gitwildmatch import GitWildMatchPattern

GITIGNORE_FILENAME = ".gitignore"
CUSTOM_EXCLUDE_FILENAME = "excluded_files.txt"
FILE_SEPARATOR = "————————————"
OUTPUT_SEPARATOR = "————"
SUPPORTED_FORMATS = {"text", "markdown"}


@dataclass(frozen=True)
class ExtractedFile:
    """A text file included in an extraction."""

    path: str
    content: str


@dataclass(frozen=True)
class SkippedFile:
    """A file skipped during extraction, with a human-readable reason."""

    path: str
    reason: str


@dataclass(frozen=True)
class ExtractionResult:
    """The rendered output and metadata for an extraction run."""

    content: str
    files: tuple[ExtractedFile, ...]
    skipped_files: tuple[SkippedFile, ...]
    output_format: str


@dataclass(frozen=True)
class _IgnoreRuleSet:
    base: str
    spec: GitIgnoreSpec


def _compile_gitwildmatch_pattern(pattern_text: str) -> GitWildMatchPattern:
    with warnings.catch_warnings():
        # pathspec compiles some valid gitignore character classes to regexes
        # that trigger this Python implementation warning.
        warnings.filterwarnings(
            "ignore",
            message=r"Possible nested set at position \d+",
            category=FutureWarning,
        )
        return GitWildMatchPattern(pattern_text)


@lru_cache(maxsize=1024)
def _compile_direct_directory_pattern(pattern_text: str) -> GitWildMatchPattern:
    return _compile_gitwildmatch_pattern(pattern_text)


class ProjectCodeExtractor:
    """Extract text file contents from a project directory."""

    def __init__(
        self,
        project_path: str | os.PathLike[str],
        include_hidden: bool = False,
        additional_exclude_patterns: Sequence[str] | None = None,
        encoding: str = "utf-8",
        output_format: str = "text",
        max_file_size: int | None = None,
        follow_symlinks: bool = False,
        excluded_paths: Sequence[str | os.PathLike[str]] | None = None,
    ):
        self.project_path = Path(project_path).expanduser().resolve()
        if not self.project_path.exists():
            raise FileNotFoundError(f"Project path does not exist: {self.project_path}")
        if not self.project_path.is_dir():
            raise NotADirectoryError(
                f"Project path is not a directory: {self.project_path}"
            )
        if output_format not in SUPPORTED_FORMATS:
            supported = ", ".join(sorted(SUPPORTED_FORMATS))
            raise ValueError(
                f"Unsupported output format {output_format!r}; expected one of: {supported}"
            )
        if max_file_size is not None and max_file_size < 0:
            raise ValueError("max_file_size must be non-negative")
        try:
            codecs.lookup(encoding)
        except LookupError as exc:
            raise ValueError(f"Unknown text encoding: {encoding}") from exc

        self.include_hidden = include_hidden
        self.additional_exclude_patterns = tuple(additional_exclude_patterns or ())
        self.encoding = encoding
        self.output_format = output_format
        self.max_file_size = max_file_size
        self.follow_symlinks = follow_symlinks
        self.excluded_paths = self._relative_excluded_paths(excluded_paths or ())

        # Kept for compatibility with the original script's public attributes.
        self.output: list[str] = []
        self.excluded_patterns = self._public_excluded_patterns()

        self.included_files: list[str] = []
        self.skipped_files: list[SkippedFile] = []
        self.last_result: ExtractionResult | None = None
        self._gitignore_rule_sets: list[_IgnoreRuleSet] = []
        self._custom_rule_sets: list[_IgnoreRuleSet] = []
        self._root_rules_loaded = False

    def load_exclusions(self, filename: str) -> list[str]:
        """Load raw exclusion lines from a file in the project root.

        This method is retained for compatibility with the original script.
        """
        file_path = self.project_path / filename
        if not file_path.exists():
            return []
        return [
            line.strip()
            for line in file_path.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]

    def _public_excluded_patterns(self) -> list[str]:
        return (
            self.load_exclusions(GITIGNORE_FILENAME)
            + self.load_exclusions(CUSTOM_EXCLUDE_FILENAME)
            + list(self.additional_exclude_patterns)
        )

    def is_excluded(self, path: str | os.PathLike[str]) -> bool:
        """Return whether *path* is excluded by the currently loaded rules."""
        if not self._root_rules_loaded:
            self._load_root_rule_sets()
        candidate = Path(path)
        if candidate.is_absolute():
            try:
                relative_path = (
                    candidate.resolve().relative_to(self.project_path).as_posix()
                )
            except ValueError:
                return False
        else:
            relative_path = candidate.as_posix()
        return self._is_ignored(relative_path, candidate.is_dir())

    def extract_code(self) -> ExtractionResult:
        """Walk the project, read eligible text files, and render the output."""
        self._gitignore_rule_sets = []
        self._custom_rule_sets = []
        self._load_root_rule_sets()

        extracted: list[ExtractedFile] = []
        skipped: list[SkippedFile] = []

        for root, dirs, files in self._walk_project():
            root_path = Path(root)
            relative_root = self._relative_posix(root_path)

            # Nested .gitignore files apply to their own directory tree and are
            # evaluated after ignore files from parent directories.
            if relative_root:
                self._load_ignore_file(
                    root_path / GITIGNORE_FILENAME,
                    relative_root,
                    self._gitignore_rule_sets,
                )

            dirs.sort(key=lambda value: (value.lower(), value))
            files.sort(key=lambda value: (value.lower(), value))

            kept_dirs = []
            for dirname in dirs:
                if dirname == ".git":
                    continue
                if not self.include_hidden and dirname.startswith("."):
                    continue
                relative_dir = self._join_relative(relative_root, dirname)
                if self._is_ignored(relative_dir, is_dir=True):
                    continue
                kept_dirs.append(dirname)
            dirs[:] = kept_dirs

            for filename in files:
                if not self.include_hidden and filename.startswith("."):
                    continue

                relative_file = self._join_relative(relative_root, filename)
                file_path = root_path / filename

                if relative_file == CUSTOM_EXCLUDE_FILENAME:
                    skipped.append(
                        SkippedFile(relative_file, "extractor configuration file")
                    )
                    continue
                if relative_file in self.excluded_paths:
                    skipped.append(
                        SkippedFile(relative_file, "explicitly excluded path")
                    )
                    continue
                if self._is_ignored(relative_file, is_dir=False):
                    skipped.append(
                        SkippedFile(relative_file, "excluded by ignore pattern")
                    )
                    continue
                if file_path.is_symlink() and not self.follow_symlinks:
                    skipped.append(SkippedFile(relative_file, "symlink skipped"))
                    continue

                try:
                    if not file_path.is_file():
                        skipped.append(SkippedFile(relative_file, "not a regular file"))
                        continue
                    file_size = file_path.stat().st_size
                except OSError as exc:
                    skipped.append(
                        SkippedFile(relative_file, f"cannot stat file: {exc}")
                    )
                    continue

                if self.max_file_size is not None and file_size > self.max_file_size:
                    skipped.append(
                        SkippedFile(
                            relative_file,
                            f"file is larger than {self.max_file_size} bytes",
                        )
                    )
                    continue

                try:
                    data = file_path.read_bytes()
                except OSError as exc:
                    skipped.append(
                        SkippedFile(relative_file, f"cannot read file: {exc}")
                    )
                    continue

                try:
                    text = data.decode(self.encoding)
                except UnicodeDecodeError:
                    skipped.append(
                        SkippedFile(relative_file, f"not valid {self.encoding} text")
                    )
                    continue

                if self._looks_binary(text):
                    skipped.append(SkippedFile(relative_file, "binary file"))
                    continue

                extracted.append(ExtractedFile(relative_file, text))

        extracted.sort(key=lambda item: (item.path.lower(), item.path))
        self.output = [
            self.format_file_content(item.path, item.content) for item in extracted
        ]
        content = self._render_output()
        self.included_files = [item.path for item in extracted]
        self.skipped_files = skipped

        result = ExtractionResult(
            content=content,
            files=tuple(extracted),
            skipped_files=tuple(skipped),
            output_format=self.output_format,
        )
        self.last_result = result
        self.excluded_patterns = self._public_excluded_patterns()
        return result

    def format_file_content(
        self, file_path: str | os.PathLike[str], content: str | None = None
    ) -> str:
        """Format one file in the selected output format.

        When *content* is omitted, *file_path* is read from disk. This keeps the
        method compatible with the original script.
        """
        path = Path(file_path)
        if content is None:
            content = path.read_text(encoding=self.encoding, errors="ignore")

        display_path = self._display_path(path)
        body = content if content.endswith("\n") or not content else content + "\n"

        if self.output_format == "markdown":
            fence = self._markdown_fence(content)
            language = self._language_for_path(display_path)
            return f"## `{display_path}`\n\n{fence}{language}\n{body}{fence}\n"

        return f"{FILE_SEPARATOR}\n{display_path}:\n\n{body}{FILE_SEPARATOR}\n"

    def save_to_clipboard(self, content: str | None = None) -> None:
        """Copy rendered output to the system clipboard."""
        if content is None:
            if self.last_result is None:
                raise RuntimeError("Run extract_code() before saving to the clipboard")
            content = self.last_result.content
        pyperclip.copy(content)
        try:
            clipboard_content = pyperclip.paste()
        except Exception as exc:
            raise pyperclip.PyperclipException(
                "copy to clipboard could not be verified"
            ) from exc
        if clipboard_content != content:
            raise pyperclip.PyperclipException(
                "copy to clipboard could not be verified"
            )

    def run(self) -> ExtractionResult:
        """Extract the project and copy the rendered output to the clipboard."""
        result = self.extract_code()
        self.save_to_clipboard(result.content)
        print("Code extracted and copied to clipboard!")
        return result

    def _walk_project(self) -> Iterator[tuple[str, list[str], list[str]]]:
        if not self.follow_symlinks:
            yield from os.walk(self.project_path, topdown=True, followlinks=False)
            return

        ancestor_chains: dict[str, tuple[tuple[int, int], ...]] = {}
        for root, dirs, files in os.walk(
            self.project_path, topdown=True, followlinks=True
        ):
            normalized_root = os.path.normpath(root)
            ancestor_chain = ancestor_chains.pop(normalized_root, ())

            try:
                stat_result = os.stat(root)
            except OSError:
                stat_result = None

            if stat_result is not None:
                directory_key = (stat_result.st_dev, stat_result.st_ino)
                if directory_key in ancestor_chain:
                    dirs[:] = []
                    continue
                ancestor_chain = (*ancestor_chain, directory_key)

            # Track ancestors independently for each logical path. A symlinked
            # directory may alias another part of the tree without hiding that
            # part, while a link back to one of its own ancestors is still a
            # cycle and must not be entered.
            for dirname in dirs:
                child_path = os.path.normpath(os.path.join(root, dirname))
                ancestor_chains[child_path] = ancestor_chain
            yield root, dirs, files

    def _relative_excluded_paths(
        self, paths: Iterable[str | os.PathLike[str]]
    ) -> set[str]:
        relative_paths: set[str] = set()
        for path in paths:
            resolved_path = Path(path).expanduser().resolve()
            try:
                relative_path = resolved_path.relative_to(self.project_path).as_posix()
            except ValueError:
                continue
            if relative_path != ".":
                relative_paths.add(relative_path)
        return relative_paths

    def _load_root_rule_sets(self) -> None:
        self._load_ignore_file(
            self.project_path / GITIGNORE_FILENAME,
            "",
            self._gitignore_rule_sets,
        )
        self._load_ignore_file(
            self.project_path / CUSTOM_EXCLUDE_FILENAME,
            "",
            self._custom_rule_sets,
        )
        if self.additional_exclude_patterns:
            try:
                additional_spec = GitIgnoreSpec.from_lines(
                    self.additional_exclude_patterns
                )
            except ValueError as exc:
                raise ValueError(
                    f"Invalid additional exclusion pattern: {exc}"
                ) from exc
            self._custom_rule_sets.append(_IgnoreRuleSet("", additional_spec))
        self._root_rules_loaded = True

    def _load_ignore_file(
        self, file_path: Path, base: str, target: list[_IgnoreRuleSet]
    ) -> None:
        if not file_path.is_file():
            return
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
        spec = self._compile_lenient_gitignore_spec(lines, str(file_path))
        target.append(_IgnoreRuleSet(base, spec))

    @staticmethod
    def _compile_lenient_gitignore_spec(
        lines: Iterable[str], source: str
    ) -> GitIgnoreSpec:
        compiled_patterns = []
        for line_number, line in enumerate(lines, start=1):
            try:
                compiled_patterns.append(_compile_gitwildmatch_pattern(line))
            except ValueError as exc:
                warnings.warn(
                    f"Skipping invalid ignore pattern in {source}:{line_number}: {line!r} ({exc})",
                    UserWarning,
                    stacklevel=3,
                )
                continue
        return GitIgnoreSpec(compiled_patterns)

    def _relative_posix(self, path: Path) -> str:
        relative = path.relative_to(self.project_path)
        if str(relative) == ".":
            return ""
        return relative.as_posix()

    @staticmethod
    def _join_relative(base: str, name: str) -> str:
        return f"{base}/{name}" if base else name

    def _display_path(self, path: Path) -> str:
        if not path.is_absolute():
            return path.as_posix()
        try:
            return path.resolve().relative_to(self.project_path).as_posix()
        except (OSError, ValueError):
            return path.as_posix()

    def _is_ignored(self, relative_path: str, is_dir: bool) -> bool:
        if not relative_path:
            return False

        gitignore_result = self._match_rule_sets(
            relative_path, is_dir, self._gitignore_rule_sets
        )
        custom_result = self._match_rule_sets(
            relative_path, is_dir, self._custom_rule_sets
        )

        ignored = bool(gitignore_result) if gitignore_result is not None else False
        if custom_result is not None:
            ignored = custom_result
        return ignored

    @staticmethod
    def _match_rule_sets(
        relative_path: str,
        is_dir: bool,
        rule_sets: Iterable[_IgnoreRuleSet],
    ) -> bool | None:
        result: bool | None = None
        for rule_set in rule_sets:
            candidate = ProjectCodeExtractor._candidate_for_rule_set(
                relative_path, rule_set.base
            )
            if candidate is None:
                continue
            for pattern in rule_set.spec.patterns:
                if pattern.include is None:
                    continue
                if ProjectCodeExtractor._pattern_matches_directly(
                    pattern, candidate, is_dir
                ):
                    result = bool(pattern.include)
        return result

    @staticmethod
    def _pattern_matches_directly(pattern, candidate: str, is_dir: bool) -> bool:
        """Match a gitignore pattern against one path without inheriting parent matches.

        pathspec intentionally also matches descendants of matched directories.
        Git applies that part through directory traversal instead. Since this
        extractor already prunes ignored directories, considering parent matches
        again would make negations such as ``!build`` incorrectly re-include
        files inside ``build`` that were excluded by independent patterns.
        """
        pattern_text = pattern.pattern
        if pattern_text.endswith("\\ "):
            # pathspec preserves a trailing escaped space but otherwise strips
            # whitespace before compiling the pattern.
            pattern_text = pattern_text.lstrip()
        else:
            pattern_text = pattern_text.strip()

        if pattern_text.endswith("/"):
            if not is_dir:
                return False
            direct_text = pattern_text[:-1]
            if not direct_text:
                return False
            direct_pattern = _compile_direct_directory_pattern(direct_text)
            if direct_pattern.include is None:
                return False
            match = direct_pattern.match_file(candidate)
        else:
            match = pattern.match_file(candidate)

        if match is None:
            return False
        return match.match.groupdict().get("ps_d") is None

    @staticmethod
    def _candidate_for_rule_set(relative_path: str, base: str) -> str | None:
        if base:
            prefix = f"{base}/"
            if not relative_path.startswith(prefix):
                return None
            candidate = relative_path[len(prefix) :]
        else:
            candidate = relative_path

        if not candidate:
            return None
        return candidate

    @staticmethod
    def _looks_binary(text: str, sample_size: int = 8192) -> bool:
        sample = text[:sample_size]
        if not sample:
            return False
        if "\x00" in sample:
            return True
        control_characters = sum(
            1
            for character in sample
            if ord(character) < 32 and character not in {"\n", "\r", "\t", "\f", "\b"}
        )
        return control_characters / len(sample) > 0.30

    @staticmethod
    def _markdown_fence(content: str) -> str:
        longest_run = max(
            (len(match) for match in re.findall(r"`+", content)), default=0
        )
        return "`" * max(3, longest_run + 1)

    @staticmethod
    def _language_for_path(path: str) -> str:
        extension = Path(path).suffix.lower().lstrip(".")
        language_map = {
            "py": "python",
            "sh": "bash",
            "bash": "bash",
            "zsh": "bash",
            "yml": "yaml",
            "js": "javascript",
            "ts": "typescript",
            "tsx": "tsx",
            "jsx": "jsx",
            "cs": "csharp",
            "cpp": "cpp",
            "cxx": "cpp",
            "hpp": "cpp",
            "rb": "ruby",
            "rs": "rust",
        }
        return language_map.get(extension, extension)

    def _render_output(self) -> str:
        if not self.output:
            return ""

        if self.output_format == "markdown":
            return "\n".join(chunk.rstrip() for chunk in self.output) + "\n"

        return (
            f"{OUTPUT_SEPARATOR}\n" + "\n".join(self.output) + f"{OUTPUT_SEPARATOR}\n"
        )
