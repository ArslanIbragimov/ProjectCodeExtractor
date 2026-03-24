use anyhow::Result;
use content_inspector::{ContentType, inspect};
use ignore::WalkBuilder;
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ExtractedFile {
    pub relative_path: PathBuf,
    pub contents: String,
}

#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub struct ExtractionStats {
    pub extracted_files: usize,
    pub skipped_binary_files: usize,
    pub skipped_output_targets: usize,
    pub skipped_errors: usize,
}

#[derive(Debug, Default)]
pub struct ExtractionReport {
    pub files: Vec<ExtractedFile>,
    pub stats: ExtractionStats,
}

pub struct ProjectExtractor {
    root: PathBuf,
    include_hidden: bool,
    excluded_file_name: String,
    extra_excluded_paths: Vec<PathBuf>,
    verbose: bool,
}

impl ProjectExtractor {
    pub fn new(
        root: PathBuf,
        include_hidden: bool,
        excluded_file_name: String,
        extra_excluded_paths: Vec<PathBuf>,
        verbose: bool,
    ) -> Self {
        Self {
            root,
            include_hidden,
            excluded_file_name,
            extra_excluded_paths,
            verbose,
        }
    }

    pub fn extract(&self) -> Result<ExtractionReport> {
        let mut builder = WalkBuilder::new(&self.root);
        builder.hidden(!self.include_hidden);
        builder.ignore(false);
        builder.git_ignore(true);
        builder.git_exclude(false);
        builder.git_global(false);
        builder.parents(false);
        builder.require_git(false);

        if !self.excluded_file_name.trim().is_empty() {
            builder.add_custom_ignore_filename(&self.excluded_file_name);
        }

        let mut report = ExtractionReport::default();

        for entry in builder.build() {
            let entry = match entry {
                Ok(entry) => entry,
                Err(error) => {
                    report.stats.skipped_errors += 1;
                    if self.verbose {
                        eprintln!("Skipping path due to walk error: {error}");
                    }
                    continue;
                }
            };

            let Some(file_type) = entry.file_type() else {
                continue;
            };

            if !file_type.is_file() {
                continue;
            }

            let path = entry.into_path();

            if self.is_explicitly_excluded(&path) {
                report.stats.skipped_output_targets += 1;
                if self.verbose {
                    eprintln!("Skipping explicit output target: {}", path.display());
                }
                continue;
            }

            let bytes = match fs::read(&path) {
                Ok(bytes) => bytes,
                Err(error) => {
                    report.stats.skipped_errors += 1;
                    if self.verbose {
                        eprintln!("Skipping unreadable file {}: {}", path.display(), error);
                    }
                    continue;
                }
            };

            if matches!(inspect(&bytes), ContentType::BINARY) {
                report.stats.skipped_binary_files += 1;
                if self.verbose {
                    eprintln!("Skipping binary file: {}", path.display());
                }
                continue;
            }

            let relative_path = path.strip_prefix(&self.root).unwrap_or(&path).to_path_buf();
            report.files.push(ExtractedFile {
                relative_path,
                contents: decode_text(&bytes),
            });
        }

        report
            .files
            .sort_by(|left, right| left.relative_path.cmp(&right.relative_path));
        report.stats.extracted_files = report.files.len();

        Ok(report)
    }

    fn is_explicitly_excluded(&self, path: &Path) -> bool {
        self.extra_excluded_paths
            .iter()
            .any(|candidate| candidate == path)
    }
}

fn decode_text(bytes: &[u8]) -> String {
    let text = String::from_utf8_lossy(bytes).into_owned();
    text.strip_prefix('\u{feff}')
        .unwrap_or(text.as_str())
        .to_owned()
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    #[test]
    fn respects_gitignore_and_custom_ignore_files() {
        let temp_dir = TempDir::new().unwrap();
        let root = temp_dir.path();

        write_file(root, ".gitignore", b"ignored.rs\nnested/\n");
        write_file(root, "excluded_files.txt", b"*.md\n");
        write_file(root, "src/lib.rs", b"pub fn value() -> i32 { 42 }\n");
        write_file(root, "ignored.rs", b"fn ignored() {}\n");
        write_file(root, "README.md", b"# docs\n");
        write_file(root, "nested/skip.txt", b"skip me\n");
        write_file(root, ".secret", b"top-secret\n");
        write_file(root, "data.bin", b"\0\0\0\0");

        let report = ProjectExtractor::new(
            root.to_path_buf(),
            false,
            "excluded_files.txt".to_owned(),
            Vec::new(),
            false,
        )
        .extract()
        .unwrap();

        let paths = rendered_paths(&report.files);
        assert!(paths.contains(&"src/lib.rs".to_owned()));
        assert!(!paths.contains(&"ignored.rs".to_owned()));
        assert!(!paths.contains(&"README.md".to_owned()));
        assert!(!paths.contains(&"nested/skip.txt".to_owned()));
        assert!(!paths.contains(&".secret".to_owned()));
        assert!(!paths.contains(&"data.bin".to_owned()));
        assert_eq!(report.stats.skipped_binary_files, 1);
    }

    #[test]
    fn can_include_hidden_files() {
        let temp_dir = TempDir::new().unwrap();
        let root = temp_dir.path();

        write_file(root, ".env", b"TOKEN=secret\n");

        let report = ProjectExtractor::new(
            root.to_path_buf(),
            true,
            "excluded_files.txt".to_owned(),
            Vec::new(),
            false,
        )
        .extract()
        .unwrap();

        let paths = rendered_paths(&report.files);
        assert!(paths.contains(&".env".to_owned()));
    }

    #[test]
    fn skips_configured_output_target() {
        let temp_dir = TempDir::new().unwrap();
        let root = temp_dir.path();
        let bundle_path = root.join("bundle.txt");

        write_file(root, "main.rs", b"fn main() {}\n");
        write_file(root, "bundle.txt", b"old bundle\n");

        let report = ProjectExtractor::new(
            root.to_path_buf(),
            false,
            "excluded_files.txt".to_owned(),
            vec![bundle_path],
            false,
        )
        .extract()
        .unwrap();

        let paths = rendered_paths(&report.files);
        assert!(paths.contains(&"main.rs".to_owned()));
        assert!(!paths.contains(&"bundle.txt".to_owned()));
        assert_eq!(report.stats.skipped_output_targets, 1);
    }

    #[test]
    fn strips_utf8_bom_when_decoding_text() {
        let temp_dir = TempDir::new().unwrap();
        let root = temp_dir.path();

        write_file(root, "bom.txt", b"\xEF\xBB\xBFhello\n");

        let report = ProjectExtractor::new(
            root.to_path_buf(),
            false,
            "excluded_files.txt".to_owned(),
            Vec::new(),
            false,
        )
        .extract()
        .unwrap();

        assert_eq!(report.files[0].contents, "hello\n");
    }

    #[test]
    fn sorts_files_by_relative_path() {
        let temp_dir = TempDir::new().unwrap();
        let root = temp_dir.path();

        write_file(root, "zeta.txt", b"z\n");
        write_file(root, "alpha.txt", b"a\n");

        let report = ProjectExtractor::new(
            root.to_path_buf(),
            false,
            "excluded_files.txt".to_owned(),
            Vec::new(),
            false,
        )
        .extract()
        .unwrap();

        assert_eq!(
            rendered_paths(&report.files),
            vec!["alpha.txt".to_owned(), "zeta.txt".to_owned()]
        );
    }

    fn rendered_paths(files: &[ExtractedFile]) -> Vec<String> {
        files
            .iter()
            .map(|file| file.relative_path.to_string_lossy().replace('\\', "/"))
            .collect()
    }

    fn write_file(root: &Path, relative_path: &str, bytes: &[u8]) {
        let path = relative_path
            .split('/')
            .fold(root.to_path_buf(), |path, segment| path.join(segment));

        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent).unwrap();
        }

        fs::write(path, bytes).unwrap();
    }
}
