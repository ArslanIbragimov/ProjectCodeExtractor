use std::fs;

use project_code_extractor::{Cli, run};
use tempfile::TempDir;

fn write_file(project_dir: &TempDir, relative_path: &str, contents: &[u8]) {
    let file_path = project_dir.path().join(relative_path);
    if let Some(parent) = file_path.parent() {
        fs::create_dir_all(parent).unwrap();
    }

    fs::write(file_path, contents).unwrap();
}

#[test]
fn run_writes_bundle_and_respects_ignore_rules() {
    let project_dir = TempDir::new().unwrap();
    let output_path = project_dir.path().join("bundle.txt");

    write_file(&project_dir, ".gitignore", b"*.log\nignored/\n");
    write_file(&project_dir, "excluded_files.txt", b"*.md\n");
    write_file(
        &project_dir,
        "src/lib.rs",
        b"pub fn value() -> i32 { 42 }\n",
    );
    write_file(&project_dir, "notes.log", b"ignore me\n");
    write_file(&project_dir, "README.md", b"# docs\n");
    write_file(&project_dir, "ignored/file.txt", b"ignore me too\n");

    run(Cli {
        project_path: project_dir.path().to_path_buf(),
        output: Some(output_path.clone()),
        stdout: false,
        no_clipboard: true,
        include_hidden: false,
        excluded_file_name: "excluded_files.txt".to_owned(),
        verbose: false,
    })
    .unwrap();

    let output = fs::read_to_string(output_path).unwrap();
    assert!(output.contains("src/lib.rs"));
    assert!(!output.contains("notes.log"));
    assert!(!output.contains("README.md"));
    assert!(!output.contains("ignored/file.txt"));
}

#[test]
fn run_can_include_hidden_files() {
    let project_dir = TempDir::new().unwrap();
    let output_path = project_dir.path().join("bundle.txt");

    write_file(&project_dir, ".env", b"TOKEN=secret\n");

    run(Cli {
        project_path: project_dir.path().to_path_buf(),
        output: Some(output_path.clone()),
        stdout: false,
        no_clipboard: true,
        include_hidden: true,
        excluded_file_name: "excluded_files.txt".to_owned(),
        verbose: false,
    })
    .unwrap();

    let output = fs::read_to_string(output_path).unwrap();
    assert!(output.contains(".env"));
    assert!(output.contains("TOKEN=secret"));
}
