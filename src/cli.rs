use clap::Parser;
use std::path::PathBuf;

#[derive(Debug, Clone, Parser)]
#[command(
    name = "project-code-extractor",
    version,
    about = "Extract project source files into a single shareable document."
)]
pub struct Cli {
    #[arg(value_name = "PATH", default_value = ".")]
    pub project_path: PathBuf,

    #[arg(short, long, value_name = "FILE")]
    pub output: Option<PathBuf>,

    #[arg(long, help = "Print the extracted bundle to stdout.")]
    pub stdout: bool,

    #[arg(long, help = "Do not copy the extracted bundle to the clipboard.")]
    pub no_clipboard: bool,

    #[arg(long, help = "Include hidden files and directories in the output.")]
    pub include_hidden: bool,

    #[arg(
        long,
        default_value = "excluded_files.txt",
        value_name = "NAME",
        help = "Additional ignore-file name to load alongside .gitignore."
    )]
    pub excluded_file_name: String,

    #[arg(short, long, help = "Print non-fatal skip details to stderr.")]
    pub verbose: bool,
}
