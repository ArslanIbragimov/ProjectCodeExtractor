pub mod cli;
mod clipboard;
mod extractor;
mod formatter;

pub use cli::Cli;

use anyhow::{Context, Result, bail};
use extractor::ProjectExtractor;
use std::fs;
use std::path::{Path, PathBuf};

pub fn run(cli: Cli) -> Result<()> {
    let project_path = normalize_existing_directory(&cli.project_path)?;
    let output_path = cli.output.as_deref().map(normalize_path).transpose()?;

    if cli.no_clipboard && output_path.is_none() && !cli.stdout {
        bail!("no output destination selected; remove --no-clipboard or add --output/--stdout");
    }

    let mut extra_excluded_paths = Vec::new();
    if let Some(path) = &output_path {
        extra_excluded_paths.push(normalize_comparison_path(path)?);
    }

    let extractor = ProjectExtractor::new(
        project_path,
        cli.include_hidden,
        cli.excluded_file_name,
        extra_excluded_paths,
        cli.verbose,
    );

    let report = extractor.extract()?;
    let rendered = formatter::render(&report.files);

    if let Some(path) = &output_path {
        if let Some(parent) = path.parent() {
            if !parent.as_os_str().is_empty() {
                fs::create_dir_all(parent).with_context(|| {
                    format!("failed to create output directory {}", parent.display())
                })?;
            }
        }

        fs::write(path, &rendered)
            .with_context(|| format!("failed to write output file {}", path.display()))?;
        eprintln!("Wrote extracted code to {}", path.display());
    }

    if cli.stdout {
        print!("{rendered}");
        if !rendered.is_empty() && !rendered.ends_with('\n') {
            println!();
        }
    }

    if !cli.no_clipboard {
        if rendered.is_empty() {
            eprintln!("No matching text files were found; clipboard was not updated.");
        } else {
            clipboard::copy(&rendered)?;
            eprintln!("Copied extracted code to the system clipboard.");
        }
    }

    eprintln!(
        "Extracted {} file(s); skipped {} binary file(s), {} explicit output target(s), {} walk/read error(s).",
        report.stats.extracted_files,
        report.stats.skipped_binary_files,
        report.stats.skipped_output_targets,
        report.stats.skipped_errors
    );

    Ok(())
}

fn normalize_existing_directory(path: &Path) -> Result<PathBuf> {
    let resolved = path
        .canonicalize()
        .with_context(|| format!("failed to resolve project path {}", path.display()))?;

    if !resolved.is_dir() {
        bail!("project path is not a directory: {}", resolved.display());
    }

    Ok(resolved)
}

fn normalize_path(path: &Path) -> Result<PathBuf> {
    if path.is_absolute() {
        return Ok(path.to_path_buf());
    }

    let cwd = std::env::current_dir().context("failed to resolve current working directory")?;
    Ok(cwd.join(path))
}

fn normalize_comparison_path(path: &Path) -> Result<PathBuf> {
    if path.exists() {
        return path
            .canonicalize()
            .with_context(|| format!("failed to resolve output path {}", path.display()));
    }

    Ok(path.to_path_buf())
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    #[test]
    fn rejects_configuration_without_any_output_destination() {
        let temp_dir = TempDir::new().unwrap();
        let cli = Cli {
            project_path: temp_dir.path().to_path_buf(),
            output: None,
            stdout: false,
            no_clipboard: true,
            include_hidden: false,
            excluded_file_name: "excluded_files.txt".to_owned(),
            verbose: false,
        };

        let error = run(cli).unwrap_err();

        assert!(
            error.to_string().contains("no output destination selected"),
            "unexpected error: {error:#}"
        );
    }

    #[test]
    fn writes_bundle_to_output_file_and_skips_existing_bundle_from_input() {
        let temp_dir = TempDir::new().unwrap();
        let root = temp_dir.path();
        let output_path = root.join("bundle.txt");

        fs::write(root.join("main.rs"), "fn main() {}\n").unwrap();
        fs::write(&output_path, "old bundle contents\n").unwrap();

        let cli = Cli {
            project_path: root.to_path_buf(),
            output: Some(output_path.clone()),
            stdout: false,
            no_clipboard: true,
            include_hidden: false,
            excluded_file_name: "excluded_files.txt".to_owned(),
            verbose: false,
        };

        run(cli).unwrap();

        let rendered = fs::read_to_string(output_path).unwrap();
        assert!(rendered.contains("main.rs"));
        assert!(rendered.contains("fn main() {}"));
        assert!(!rendered.contains("old bundle contents"));
        assert!(!rendered.contains("bundle.txt"));
    }
}
