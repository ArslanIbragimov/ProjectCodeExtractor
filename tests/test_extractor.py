import os
import shutil
import subprocess
from pathlib import Path

import pyperclip
import pytest

from project_code_extractor import ProjectCodeExtractor


def write_file(root: Path, relative_path: str, content: str = "content") -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def extract_paths(result):
    return [item.path for item in result.files]


def test_extracts_text_files_in_deterministic_order(tmp_path):
    write_file(tmp_path, "b.py", "print('b')\n")
    write_file(tmp_path, "a.py", "print('a')\n")
    write_file(tmp_path, "nested/c.py", "print('c')\n")
    write_file(tmp_path, "z.py", "print('z')\n")

    result = ProjectCodeExtractor(tmp_path).extract_code()

    assert extract_paths(result) == ["a.py", "b.py", "nested/c.py", "z.py"]
    assert result.content.startswith("————\n")
    assert "a.py:\n\nprint('a')\n" in result.content
    assert result.skipped_files == ()


def test_root_gitignore_uses_git_wildmatch_semantics(tmp_path):
    write_file(
        tmp_path,
        ".gitignore",
        "*.log\nbuild/\n/root-only.txt\ndocs/*.md\n!docs/keep.md\n",
    )
    write_file(tmp_path, "app.py")
    write_file(tmp_path, "debug.log")
    write_file(tmp_path, "build/output.py")
    write_file(tmp_path, "root-only.txt")
    write_file(tmp_path, "sub/root-only.txt")
    write_file(tmp_path, "docs/temp.md")
    write_file(tmp_path, "docs/keep.md")

    result = ProjectCodeExtractor(tmp_path).extract_code()

    assert extract_paths(result) == ["app.py", "docs/keep.md", "sub/root-only.txt"]
    skipped = {item.path for item in result.skipped_files}
    assert {"debug.log", "root-only.txt", "docs/temp.md"}.issubset(skipped)


def test_nested_gitignore_can_reinclude_files(tmp_path):
    write_file(tmp_path, ".gitignore", "*.tmp\n")
    write_file(tmp_path, "sub/.gitignore", "!keep.tmp\n")
    write_file(tmp_path, "root.tmp")
    write_file(tmp_path, "sub/keep.tmp")
    write_file(tmp_path, "sub/other.tmp")

    result = ProjectCodeExtractor(tmp_path).extract_code()

    assert extract_paths(result) == ["sub/keep.tmp"]


def test_excluded_directory_is_not_reincluded_by_negation(tmp_path):
    write_file(tmp_path, ".gitignore", "ignored/\n!ignored/keep.py\n")
    write_file(tmp_path, "ignored/keep.py")
    write_file(tmp_path, "visible.py")

    result = ProjectCodeExtractor(tmp_path).extract_code()

    assert extract_paths(result) == ["visible.py"]


def test_reincluded_directory_does_not_override_independent_file_exclusions(tmp_path):
    write_file(tmp_path, ".gitignore", "*.py\n!build\n")
    write_file(tmp_path, "build/a.py")
    write_file(tmp_path, "build/keep.txt")

    result = ProjectCodeExtractor(tmp_path).extract_code()

    assert extract_paths(result) == ["build/keep.txt"]


def test_reincluded_directory_allows_nested_directories(tmp_path):
    write_file(tmp_path, ".gitignore", "build/\n!build\n")
    write_file(tmp_path, "build/assets/style.css")
    write_file(tmp_path, "build/output.txt")

    result = ProjectCodeExtractor(tmp_path).extract_code()

    assert extract_paths(result) == [
        "build/assets/style.css",
        "build/output.txt",
    ]


def test_reincluded_directory_does_not_override_nested_directory_exclusions(tmp_path):
    write_file(tmp_path, ".gitignore", "**/assets/\nbuild/\n!build/\n")
    write_file(tmp_path, "build/assets/style.css")
    write_file(tmp_path, "build/keep.txt")

    result = ProjectCodeExtractor(tmp_path).extract_code()

    assert extract_paths(result) == ["build/keep.txt"]


def test_trailing_space_after_directory_marker_is_ignored(tmp_path):
    write_file(tmp_path, ".gitignore", "build/ \n")
    write_file(tmp_path, "build/output.txt")
    write_file(tmp_path, "keep.txt")

    result = ProjectCodeExtractor(tmp_path).extract_code()

    assert extract_paths(result) == ["keep.txt"]


def test_double_star_contents_pattern_does_not_exclude_the_directory_itself(tmp_path):
    write_file(tmp_path, ".gitignore", "**/generated/**\n!*.py\n")
    write_file(tmp_path, "generated/a.py")
    write_file(tmp_path, "generated/b.txt")

    result = ProjectCodeExtractor(tmp_path).extract_code()

    assert extract_paths(result) == ["generated/a.py"]


def test_ignore_results_match_git_for_representative_patterns(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git executable is not available")

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    write_file(
        tmp_path,
        ".gitignore",
        "*.log\nbuild/\n/root-only.txt\ndocs/*.md\n!docs/keep.md\n**/generated/**\n!generated/reincluded.py\n",
    )
    write_file(tmp_path, "sub/.gitignore", "!nested.log\n")
    for relative_path in [
        "app.py",
        "debug.log",
        "sub/debug.log",
        "sub/nested.log",
        "build/output.txt",
        "root-only.txt",
        "sub/root-only.txt",
        "docs/temp.md",
        "docs/keep.md",
        "generated/reincluded.py",
        "generated/other.txt",
    ]:
        write_file(tmp_path, relative_path)

    git_files = set(
        subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=tmp_path,
            check=True,
            text=True,
            capture_output=True,
        ).stdout.splitlines()
    )
    result = ProjectCodeExtractor(tmp_path, include_hidden=True).extract_code()

    assert set(extract_paths(result)) == git_files


def test_invalid_gitignore_pattern_is_skipped_with_warning(tmp_path):
    write_file(tmp_path, ".gitignore", "\\\n*.py\n")
    write_file(tmp_path, "app.py")
    write_file(tmp_path, "notes.txt")

    with pytest.warns(UserWarning, match="Skipping invalid ignore pattern"):
        result = ProjectCodeExtractor(tmp_path).extract_code()

    assert extract_paths(result) == ["notes.txt"]


def test_custom_exclusion_file_overrides_gitignore_negations(tmp_path):
    write_file(tmp_path, ".gitignore", "*.txt\n!keep.txt\n")
    write_file(tmp_path, "excluded_files.txt", "keep.txt\n")
    write_file(tmp_path, "keep.txt")

    result = ProjectCodeExtractor(tmp_path).extract_code()

    assert "keep.txt" not in extract_paths(result)
    assert "excluded_files.txt" not in extract_paths(result)
    assert any(
        item.path == "excluded_files.txt"
        and item.reason == "extractor configuration file"
        for item in result.skipped_files
    )


def test_hidden_files_are_excluded_by_default_and_git_is_always_excluded(tmp_path):
    write_file(tmp_path, "visible.py")
    write_file(tmp_path, ".hidden.py")
    write_file(tmp_path, ".hidden_dir/inside.py")
    write_file(tmp_path, ".git/config")

    default_result = ProjectCodeExtractor(tmp_path).extract_code()
    include_hidden_result = ProjectCodeExtractor(
        tmp_path, include_hidden=True
    ).extract_code()

    assert extract_paths(default_result) == ["visible.py"]
    assert set(extract_paths(include_hidden_result)) == {
        ".hidden.py",
        ".hidden_dir/inside.py",
        "visible.py",
    }


def test_binary_and_invalid_text_files_are_skipped(tmp_path):
    (tmp_path / "binary.bin").write_bytes(b"abc\x00def")
    (tmp_path / "invalid.txt").write_bytes(b"\xff\xfe\xfa")
    write_file(tmp_path, "valid.py", "print('ok')\n")

    result = ProjectCodeExtractor(tmp_path).extract_code()

    assert extract_paths(result) == ["valid.py"]
    reasons = {item.path: item.reason for item in result.skipped_files}
    assert reasons["binary.bin"] == "binary file"
    assert reasons["invalid.txt"] == "not valid utf-8 text"


def test_utf16_files_can_be_extracted_with_matching_encoding(tmp_path):
    (tmp_path / "utf16.txt").write_bytes("hello utf-16".encode("utf-16"))

    result = ProjectCodeExtractor(tmp_path, encoding="utf-16").extract_code()

    assert extract_paths(result) == ["utf16.txt"]
    assert "hello utf-16" in result.content


def test_symlinked_files_are_skipped_unless_enabled(tmp_path):
    write_file(tmp_path, "target.py", "print('target')\n")
    try:
        os.symlink(tmp_path / "target.py", tmp_path / "linked.py")
    except OSError as exc:
        pytest.skip(f"symlinks are not available: {exc}")

    default_result = ProjectCodeExtractor(tmp_path).extract_code()
    follow_result = ProjectCodeExtractor(tmp_path, follow_symlinks=True).extract_code()

    assert extract_paths(default_result) == ["target.py"]
    assert default_result.skipped_files[0].path == "linked.py"
    assert extract_paths(follow_result) == ["linked.py", "target.py"]


def test_symlinked_directory_does_not_hide_the_real_tree(tmp_path):
    write_file(tmp_path, ".gitignore", "a-link/secret.py\n")
    write_file(tmp_path, "z-real/public.py")
    write_file(tmp_path, "z-real/secret.py")
    try:
        os.symlink(tmp_path / "z-real", tmp_path / "a-link")
    except OSError as exc:
        pytest.skip(f"symlinks are not available: {exc}")

    result = ProjectCodeExtractor(tmp_path, follow_symlinks=True).extract_code()

    assert extract_paths(result) == [
        "a-link/public.py",
        "z-real/public.py",
        "z-real/secret.py",
    ]


def test_directory_symlink_cycles_are_pruned(tmp_path):
    write_file(tmp_path, "a.txt")
    try:
        os.symlink(tmp_path, tmp_path / "loop")
    except OSError as exc:
        pytest.skip(f"symlinks are not available: {exc}")

    result = ProjectCodeExtractor(tmp_path, follow_symlinks=True).extract_code()

    assert extract_paths(result) == ["a.txt"]


def test_max_file_size_skips_large_files(tmp_path):
    write_file(tmp_path, "small.txt", "ok")
    write_file(tmp_path, "large.txt", "x" * 100)

    result = ProjectCodeExtractor(tmp_path, max_file_size=10).extract_code()

    assert extract_paths(result) == ["small.txt"]
    assert result.skipped_files[0].path == "large.txt"
    assert "larger than 10 bytes" in result.skipped_files[0].reason


def test_markdown_output_uses_language_and_safe_fence(tmp_path):
    write_file(tmp_path, "script.py", "```python\nprint('already fenced')\n```\n")

    result = ProjectCodeExtractor(tmp_path, output_format="markdown").extract_code()

    assert "## `script.py`" in result.content
    assert "````python\n```python" in result.content
    assert result.content.count("````") == 2


def test_clipboard_verification_failure_raises_error(tmp_path, monkeypatch):
    monkeypatch.setattr(pyperclip, "copy", lambda content: None)
    monkeypatch.setattr(pyperclip, "paste", lambda: "wrong clipboard content")

    with pytest.raises(pyperclip.PyperclipException, match="could not be verified"):
        ProjectCodeExtractor(tmp_path).save_to_clipboard("expected content")


def test_invalid_additional_exclusion_pattern_raises_clear_error(tmp_path):
    extractor = ProjectCodeExtractor(tmp_path, additional_exclude_patterns=["\\"])

    with pytest.raises(ValueError, match="Invalid additional exclusion pattern"):
        extractor.extract_code()


def test_invalid_project_path_and_format_raise_errors(tmp_path):
    with pytest.raises(FileNotFoundError):
        ProjectCodeExtractor(tmp_path / "missing")

    file_path = tmp_path / "file.txt"
    file_path.write_text("content", encoding="utf-8")
    with pytest.raises(NotADirectoryError):
        ProjectCodeExtractor(file_path)

    with pytest.raises(ValueError, match="Unsupported output format"):
        ProjectCodeExtractor(tmp_path, output_format="xml")
