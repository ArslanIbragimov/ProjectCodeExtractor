use crate::extractor::ExtractedFile;
use std::path::Path;

const SECTION_SEPARATOR: &str =
    "================================================================================";

pub fn render(files: &[ExtractedFile]) -> String {
    if files.is_empty() {
        return String::new();
    }

    files
        .iter()
        .map(format_file)
        .collect::<Vec<_>>()
        .join(&format!("\n\n{SECTION_SEPARATOR}\n\n"))
}

fn format_file(file: &ExtractedFile) -> String {
    let contents = file.contents.trim_end_matches(['\r', '\n']);

    if contents.is_empty() {
        return format!("{}\n{SECTION_SEPARATOR}", display_path(&file.relative_path));
    }

    format!(
        "{}\n{SECTION_SEPARATOR}\n{}",
        display_path(&file.relative_path),
        contents
    )
}

fn display_path(path: &Path) -> String {
    path.to_string_lossy().replace('\\', "/")
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::extractor::ExtractedFile;
    use std::path::PathBuf;

    #[test]
    fn renders_files_with_stable_separator() {
        let rendered = render(&[ExtractedFile {
            relative_path: PathBuf::from(r"src\main.rs"),
            contents: "fn main() {}\n\n".to_owned(),
        }]);

        assert_eq!(
            rendered,
            "src/main.rs\n================================================================================\nfn main() {}"
        );
    }

    #[test]
    fn renders_empty_input_as_empty_string() {
        assert!(render(&[]).is_empty());
    }

    #[test]
    fn renders_empty_file_without_extra_blank_body() {
        let rendered = render(&[ExtractedFile {
            relative_path: PathBuf::from("empty.txt"),
            contents: String::new(),
        }]);

        assert_eq!(
            rendered,
            "empty.txt\n================================================================================"
        );
    }
}
