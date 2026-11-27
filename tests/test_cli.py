import argparse

import pyperclip
import pytest

from project_code_extractor.cli import main, parse_file_size


def write_file(root, relative_path, content="print('hello')\n"):
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_output_file_destination_does_not_copy_implicitly(
    tmp_path, monkeypatch, capsys
):
    write_file(tmp_path, "app.py")
    copied = []
    monkeypatch.setattr(pyperclip, "copy", copied.append)
    output_path = tmp_path.parent / "extracted.txt"

    exit_code = main([str(tmp_path), "--output", str(output_path)])

    assert exit_code == 0
    assert copied == []
    assert "app.py" in output_path.read_text(encoding="utf-8")
    assert "Extracted 1 file(s); skipped 0 file(s)." in capsys.readouterr().err


def test_output_file_inside_project_is_not_extracted(tmp_path, monkeypatch):
    write_file(tmp_path, "app.py")
    output_path = tmp_path / "extracted.txt"
    output_path.write_text("stale extraction output\n", encoding="utf-8")
    monkeypatch.setattr(pyperclip, "copy", lambda content: None)

    exit_code = main([str(tmp_path), "--output", str(output_path), "--quiet"])

    assert exit_code == 0
    rendered = output_path.read_text(encoding="utf-8")
    assert "app.py" in rendered
    assert "extracted.txt:" not in rendered
    assert "stale extraction output" not in rendered


def test_stdout_destination_does_not_copy_implicitly(tmp_path, monkeypatch, capsys):
    write_file(tmp_path, "app.py", "print('stdout')\n")
    copied = []
    monkeypatch.setattr(pyperclip, "copy", copied.append)

    exit_code = main([str(tmp_path), "--stdout", "--quiet"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert copied == []
    assert "print('stdout')" in captured.out
    assert captured.err == ""


def test_clipboard_is_default_destination(tmp_path, monkeypatch, capsys):
    write_file(tmp_path, "app.py")
    copied = []
    monkeypatch.setattr(pyperclip, "copy", copied.append)
    monkeypatch.setattr(pyperclip, "paste", lambda: copied[-1])

    exit_code = main([str(tmp_path), "--quiet"])

    assert exit_code == 0
    assert len(copied) == 1
    assert "app.py" in copied[0]
    capsys.readouterr()


def test_clipboard_failure_returns_error(tmp_path, monkeypatch, capsys):
    write_file(tmp_path, "app.py")

    def fail_copy(content):
        raise pyperclip.PyperclipException("clipboard unavailable")

    monkeypatch.setattr(pyperclip, "copy", fail_copy)

    exit_code = main([str(tmp_path), "--quiet"])

    assert exit_code == 1
    assert "cannot copy to clipboard" in capsys.readouterr().err


def test_clipboard_can_be_combined_with_file_output(tmp_path, monkeypatch):
    write_file(tmp_path, "app.py")
    copied = []
    monkeypatch.setattr(pyperclip, "copy", copied.append)
    monkeypatch.setattr(pyperclip, "paste", lambda: copied[-1])
    output_path = tmp_path.parent / "extracted.txt"

    exit_code = main(
        [str(tmp_path), "--output", str(output_path), "--clipboard", "--quiet"]
    )

    assert exit_code == 0
    assert len(copied) == 1


def test_cli_exclude_patterns_and_exclude_file(tmp_path, monkeypatch):
    write_file(tmp_path, "keep.py")
    write_file(tmp_path, "drop.py")
    write_file(tmp_path, "drop.log")
    patterns_file = tmp_path / "patterns.txt"
    patterns_file.write_text("*.log\n", encoding="utf-8")
    copied = []
    monkeypatch.setattr(pyperclip, "copy", copied.append)
    monkeypatch.setattr(pyperclip, "paste", lambda: copied[-1])

    exit_code = main(
        [
            str(tmp_path),
            "--exclude",
            "drop.py",
            "--exclude-file",
            str(patterns_file),
            "--quiet",
        ]
    )

    assert exit_code == 0
    assert len(copied) == 1
    assert "keep.py" in copied[0]
    assert "drop.py" not in copied[0]
    assert "drop.log" not in copied[0]
    assert "patterns.txt" not in copied[0]


def test_markdown_format_is_passed_to_output(tmp_path, monkeypatch, capsys):
    write_file(tmp_path, "app.py")
    monkeypatch.setattr(pyperclip, "copy", lambda content: None)

    exit_code = main([str(tmp_path), "--format", "markdown", "--stdout", "--quiet"])

    assert exit_code == 0
    assert "## `app.py`" in capsys.readouterr().out


def test_verbose_lists_skipped_files(tmp_path, monkeypatch, capsys):
    write_file(tmp_path, "keep.py")
    write_file(tmp_path, "drop.py")
    monkeypatch.setattr(pyperclip, "copy", lambda content: None)

    exit_code = main([str(tmp_path), "--exclude", "drop.py", "--stdout", "--verbose"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "skipped drop.py: excluded by ignore pattern" in captured.err
    assert "Extracted 1 file(s); skipped 1 file(s)." in captured.err


def test_cli_formats_ignore_warnings_cleanly(tmp_path, monkeypatch, capsys):
    write_file(tmp_path, ".gitignore", "\\\n")
    write_file(tmp_path, "app.py")
    monkeypatch.setattr(pyperclip, "copy", lambda content: None)

    exit_code = main([str(tmp_path), "--stdout", "--quiet"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "warning: Skipping invalid ignore pattern" in captured.err
    assert "UserWarning" not in captured.err


def test_missing_project_returns_error(capsys):
    exit_code = main(["/definitely/missing/project", "--stdout"])

    assert exit_code == 2
    assert "Project path does not exist" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("512", 512),
        ("10KB", 10_000),
        ("2MiB", 2 * 1024 * 1024),
        ("1.5MB", 1_500_000),
    ],
)
def test_parse_file_size(value, expected):
    assert parse_file_size(value) == expected


def test_parse_file_size_rejects_invalid_values():
    with pytest.raises(argparse.ArgumentTypeError):
        parse_file_size("large")
