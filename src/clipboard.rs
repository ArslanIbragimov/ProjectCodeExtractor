use anyhow::{Context, Result};

pub fn copy(contents: &str) -> Result<()> {
    let mut clipboard =
        arboard::Clipboard::new().context("failed to access the system clipboard")?;

    clipboard
        .set_text(contents.to_owned())
        .context("failed to write extracted contents to the clipboard")?;

    Ok(())
}
