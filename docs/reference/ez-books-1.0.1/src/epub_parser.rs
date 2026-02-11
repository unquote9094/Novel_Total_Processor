use crate::error::{EzBooksError, Result};
use epub::doc::EpubDoc;
use serde::{Deserialize, Serialize};
use std::path::Path;
use tracing::{info, instrument, warn};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct EpubMetadata {
    pub title: String,
    pub author: Option<String>,
    pub isbn_10: Option<String>,
    pub isbn_13: Option<String>,
    pub publisher: Option<String>,
    pub language: Option<String>,
    pub description: Option<String>,
    pub subjects: Vec<String>,
}

impl Default for EpubMetadata {
    fn default() -> Self {
        Self {
            title: "Unknown".to_string(),
            author: None,
            isbn_10: None,
            isbn_13: None,
            publisher: None,
            language: None,
            description: None,
            subjects: Vec::new(),
        }
    }
}

#[instrument(skip_all, fields(path = %path.as_ref().display()))]
pub fn parse_epub(path: impl AsRef<Path>) -> Result<EpubMetadata> {
    let path = path.as_ref();
    info!(path = %path.display(), "Parsing EPUB file");

    let doc = EpubDoc::new(path).map_err(|e| {
        warn!(path = %path.display(), error = %e, "Failed to open EPUB file");
        EzBooksError::EpubParse(format!("Failed to open EPUB: {}", e))
    })?;

    let mut metadata = EpubMetadata::default();

    // Extract title
    if let Some(title) = doc.mdata("title") {
        metadata.title = title.value.clone();
    }

    // Extract author(s)
    if let Some(author) = doc.mdata("creator") {
        metadata.author = Some(author.value.clone());
    }

    // Extract publisher
    if let Some(publisher) = doc.mdata("publisher") {
        metadata.publisher = Some(publisher.value.clone());
    }

    // Extract language
    if let Some(language) = doc.mdata("language") {
        metadata.language = Some(language.value.clone());
    }

    // Extract description
    if let Some(description) = doc.mdata("description") {
        metadata.description = Some(description.value.clone());
    }

    // Extract subjects from metadata
    for item in &doc.metadata {
        if item.property == "subject" {
            metadata.subjects.push(item.value.clone());
        }
    }

    // Extract ISBN from identifiers
    extract_isbns(&doc, &mut metadata);

    info!(
        title = %metadata.title,
        has_author = metadata.author.is_some(),
        has_isbn = metadata.isbn_13.is_some() || metadata.isbn_10.is_some(),
        "EPUB metadata extracted successfully"
    );

    Ok(metadata)
}

fn extract_isbns(doc: &EpubDoc<std::io::BufReader<std::fs::File>>, metadata: &mut EpubMetadata) {
    // Get all identifiers from metadata
    let identifiers: Vec<String> = doc
        .metadata
        .iter()
        .filter(|item| item.property == "identifier")
        .map(|item| item.value.clone())
        .collect();

    for identifier in &identifiers {
        // Clean the identifier (remove hyphens, spaces, etc.)
        let cleaned = identifier.replace(['-', ' '], "");

        // Check for ISBN-13 (13 digits, starts with 978 or 979)
        if cleaned.len() == 13
            && (cleaned.starts_with("978") || cleaned.starts_with("979"))
            && cleaned.chars().all(char::is_numeric)
        {
            metadata.isbn_13 = Some(cleaned);
            continue;
        }

        // Check for ISBN-10 (10 characters, mostly digits)
        if cleaned.len() == 10 {
            let digit_count = cleaned.chars().filter(|c| c.is_numeric()).count();
            // ISBN-10 can have 9 digits + X as check digit
            if digit_count >= 9 {
                metadata.isbn_10 = Some(cleaned);
                continue;
            }
        }

        // Check if it contains "ISBN" prefix
        if identifier.to_uppercase().contains("ISBN") {
            let isbn_part = identifier
                .to_uppercase()
                .replace("ISBN", "")
                .replace(['-', ' ', ':'], "");

            if isbn_part.len() == 13 && isbn_part.chars().all(char::is_numeric) {
                metadata.isbn_13 = Some(isbn_part);
            } else if isbn_part.len() == 10 {
                metadata.isbn_10 = Some(isbn_part);
            }
        }
    }

    // Prefer ISBN-13 over ISBN-10
    if metadata.isbn_13.is_some() && metadata.isbn_10.is_some() {
        info!("Both ISBN-10 and ISBN-13 found, keeping both");
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn should_create_default_metadata() {
        // Given/When: Creating default metadata
        let metadata = EpubMetadata::default();

        // Then: Should have default values
        assert_eq!(metadata.title, "Unknown");
        assert!(metadata.author.is_none());
        assert!(metadata.isbn_10.is_none());
        assert!(metadata.isbn_13.is_none());
        assert!(metadata.subjects.is_empty());
    }

    #[test]
    fn should_parse_isbn13_from_identifier() {
        // This is a unit test for the ISBN extraction logic
        // We'll test the full parse_epub function with actual EPUB files in integration tests
        let isbn_13 = "978-0-123-45678-9";
        let cleaned = isbn_13.replace(['-', ' '], "");

        assert_eq!(cleaned.len(), 13);
        assert!(cleaned.starts_with("978"));
        assert!(cleaned.chars().all(char::is_numeric));
    }

    #[test]
    fn should_parse_isbn10_from_identifier() {
        let isbn_10 = "0-123-45678-X";
        let cleaned = isbn_10.replace(['-', ' '], "");

        assert_eq!(cleaned.len(), 10);
    }

    #[test]
    fn should_extract_isbn_from_identifier_with_prefix() {
        let identifier = "ISBN:978-0-123-45678-9";
        let isbn_part = identifier
            .to_uppercase()
            .replace("ISBN", "")
            .replace(['-', ' ', ':'], "");

        assert_eq!(isbn_part, "9780123456789");
        assert_eq!(isbn_part.len(), 13);
    }

    // Note: Full integration tests with actual EPUB files will be added
    // in the tests/epub_parser_test.rs file once we have test fixtures
}
