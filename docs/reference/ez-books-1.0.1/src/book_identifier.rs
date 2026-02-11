use crate::book_model::Book;
use crate::epub_parser::EpubMetadata;
use crate::error::Result;
use crate::openlibrary_client::OpenLibraryClient;
use crate::openlibrary_types::BooksApiResponse;
use tracing::{info, instrument, warn};

/// Identifies and enriches book metadata by combining EPUB metadata with OpenLibrary data
#[instrument(skip(client, epub_metadata))]
pub async fn identify_and_enrich(
    client: &OpenLibraryClient,
    epub_metadata: EpubMetadata,
    epub_path: String,
) -> Result<Book> {
    info!(
        title = %epub_metadata.title,
        has_isbn_13 = epub_metadata.isbn_13.is_some(),
        has_isbn_10 = epub_metadata.isbn_10.is_some(),
        "Identifying and enriching book metadata"
    );

    // Create base book from EPUB metadata
    let mut book = Book::new(epub_metadata.title.clone(), epub_path);

    // Copy EPUB metadata to book
    book.author = epub_metadata.author.clone();
    book.isbn_10 = epub_metadata.isbn_10.clone();
    book.isbn_13 = epub_metadata.isbn_13.clone();
    book.publisher = epub_metadata.publisher.clone();
    book.language = epub_metadata.language.clone();
    book.description = epub_metadata.description.clone();

    // Try to enrich with OpenLibrary data if we have an ISBN
    let openlibrary_data = if let Some(isbn) = epub_metadata
        .isbn_13
        .as_ref()
        .or(epub_metadata.isbn_10.as_ref())
    {
        match client.lookup_by_isbn(isbn).await {
            Ok(Some(data)) => {
                info!(isbn = %isbn, "Successfully retrieved OpenLibrary data");
                Some(data)
            }
            Ok(None) => {
                info!(isbn = %isbn, "No data found on OpenLibrary");
                None
            }
            Err(e) => {
                warn!(isbn = %isbn, error = %e, "Failed to lookup book on OpenLibrary, continuing with EPUB data only");
                None
            }
        }
    } else {
        info!("No ISBN available, skipping OpenLibrary lookup");
        None
    };

    // Merge OpenLibrary data if available
    if let Some(ol_data) = openlibrary_data {
        merge_openlibrary_data(&mut book, ol_data);
    }

    info!(
        book_id = %book.id,
        title = %book.title,
        has_author = book.author.is_some(),
        has_description = book.description.is_some(),
        has_openlibrary_key = book.openlibrary_key.is_some(),
        "Book identification and enrichment completed"
    );

    Ok(book)
}

fn merge_openlibrary_data(book: &mut Book, ol_response: BooksApiResponse) {
    // Get the first (and likely only) book data from the response
    let book_data = match ol_response.books.values().next() {
        Some(data) => data,
        None => {
            warn!("OpenLibrary response contains no book data");
            return;
        }
    };

    // Prefer OpenLibrary title if book title was "Unknown"
    if book.title == "Unknown" {
        if let Some(title) = &book_data.title {
            book.title = title.clone();
        }
    }

    // Prefer OpenLibrary author if EPUB doesn't have one
    if book.author.is_none() && !book_data.authors.is_empty() {
        book.author = Some(book_data.authors[0].name.clone());
    }

    // Always prefer OpenLibrary description (usually more complete)
    if let Some(subtitle) = &book_data.subtitle {
        let description = format!(
            "{}\n\n{}",
            book_data.title.as_deref().unwrap_or(""),
            subtitle
        );
        book.description = Some(description);
    }

    // Prefer OpenLibrary publisher if EPUB doesn't have one
    if book.publisher.is_none() && !book_data.publishers.is_empty() {
        book.publisher = Some(book_data.publishers[0].name.clone());
    }

    // Use OpenLibrary publish date if available
    if book_data.publish_date.is_some() {
        book.publish_date = book_data.publish_date.clone();
    }

    // Use page count from OpenLibrary
    if book_data.number_of_pages.is_some() {
        book.page_count = book_data.number_of_pages;
    }

    // Store OpenLibrary key for future reference
    if let Some(key) = &book_data.key {
        book.openlibrary_key = Some(key.clone());
    }

    // Extract work key from URL if available
    if let Some(url) = &book_data.url {
        if url.contains("/works/") {
            let parts: Vec<&str> = url.split("/works/").collect();
            if parts.len() > 1 {
                book.openlibrary_work_key = Some(format!("/works/{}", parts[1]));
            }
        }
    }

    info!(
        has_openlibrary_key = book.openlibrary_key.is_some(),
        has_work_key = book.openlibrary_work_key.is_some(),
        "Merged OpenLibrary data into book"
    );
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::openlibrary_types::*;
    use std::collections::HashMap;

    fn create_test_epub_metadata() -> EpubMetadata {
        EpubMetadata {
            title: "Test Book".to_string(),
            author: Some("Test Author".to_string()),
            isbn_10: None,
            isbn_13: Some("9781234567890".to_string()),
            publisher: None,
            language: Some("en".to_string()),
            description: None,
            subjects: vec!["Fiction".to_string()],
        }
    }

    fn create_test_openlibrary_response() -> BooksApiResponse {
        let mut books = HashMap::new();

        books.insert(
            "ISBN:9781234567890".to_string(),
            BookData {
                title: Some("Enhanced Test Book".to_string()),
                subtitle: Some("A Test Subtitle".to_string()),
                authors: vec![Author {
                    name: "OpenLibrary Author".to_string(),
                    url: None,
                }],
                publishers: vec![Publisher {
                    name: "Test Publisher".to_string(),
                }],
                publish_date: Some("2024".to_string()),
                number_of_pages: Some(250),
                identifiers: None,
                subjects: vec![],
                cover: None,
                url: Some("https://openlibrary.org/works/OL12345W".to_string()),
                key: Some("/books/OL12345M".to_string()),
            },
        );

        BooksApiResponse { books }
    }

    #[test]
    fn should_merge_openlibrary_publisher() {
        // Given: A book without publisher and OpenLibrary data with publisher
        let mut book = Book::new("Test".to_string(), "/path.epub".to_string());
        book.publisher = None;
        let ol_response = create_test_openlibrary_response();

        // When: Merging OpenLibrary data
        merge_openlibrary_data(&mut book, ol_response);

        // Then: Publisher should be set from OpenLibrary
        assert_eq!(book.publisher, Some("Test Publisher".to_string()));
    }

    #[test]
    fn should_merge_openlibrary_page_count() {
        // Given: A book without page count and OpenLibrary data with page count
        let mut book = Book::new("Test".to_string(), "/path.epub".to_string());
        book.page_count = None;
        let ol_response = create_test_openlibrary_response();

        // When: Merging OpenLibrary data
        merge_openlibrary_data(&mut book, ol_response);

        // Then: Page count should be set from OpenLibrary
        assert_eq!(book.page_count, Some(250));
    }

    #[test]
    fn should_store_openlibrary_keys() {
        // Given: A book and OpenLibrary data with keys
        let mut book = Book::new("Test".to_string(), "/path.epub".to_string());
        let ol_response = create_test_openlibrary_response();

        // When: Merging OpenLibrary data
        merge_openlibrary_data(&mut book, ol_response);

        // Then: OpenLibrary keys should be stored
        assert_eq!(book.openlibrary_key, Some("/books/OL12345M".to_string()));
        assert_eq!(
            book.openlibrary_work_key,
            Some("/works/OL12345W".to_string())
        );
    }

    #[test]
    fn should_preserve_epub_author_when_present() {
        // Given: A book with EPUB author and OpenLibrary data with different author
        let mut book = Book::new("Test".to_string(), "/path.epub".to_string());
        book.author = Some("EPUB Author".to_string());
        let ol_response = create_test_openlibrary_response();

        // When: Merging OpenLibrary data
        merge_openlibrary_data(&mut book, ol_response);

        // Then: EPUB author should be preserved
        assert_eq!(book.author, Some("EPUB Author".to_string()));
    }

    #[test]
    fn should_use_openlibrary_author_when_epub_missing() {
        // Given: A book without author and OpenLibrary data with author
        let mut book = Book::new("Test".to_string(), "/path.epub".to_string());
        book.author = None;
        let ol_response = create_test_openlibrary_response();

        // When: Merging OpenLibrary data
        merge_openlibrary_data(&mut book, ol_response);

        // Then: OpenLibrary author should be used
        assert_eq!(book.author, Some("OpenLibrary Author".to_string()));
    }

    #[test]
    fn should_replace_unknown_title_with_openlibrary_title() {
        // Given: A book with "Unknown" title and OpenLibrary data
        let mut book = Book::new("Unknown".to_string(), "/path.epub".to_string());
        let ol_response = create_test_openlibrary_response();

        // When: Merging OpenLibrary data
        merge_openlibrary_data(&mut book, ol_response);

        // Then: Title should be replaced with OpenLibrary title
        assert_eq!(book.title, "Enhanced Test Book");
    }

    #[test]
    fn should_set_description_from_subtitle() {
        // Given: A book without description and OpenLibrary data with subtitle
        let mut book = Book::new("Test".to_string(), "/path.epub".to_string());
        book.description = None;
        let ol_response = create_test_openlibrary_response();

        // When: Merging OpenLibrary data
        merge_openlibrary_data(&mut book, ol_response);

        // Then: Description should be set from title and subtitle
        assert!(book.description.is_some());
        let description = book.description.unwrap();
        assert!(description.contains("Enhanced Test Book"));
        assert!(description.contains("A Test Subtitle"));
    }

    #[test]
    fn should_handle_empty_openlibrary_response() {
        // Given: A book and empty OpenLibrary response
        let mut book = Book::new("Test".to_string(), "/path.epub".to_string());
        book.publisher = None;
        let ol_response = BooksApiResponse {
            books: HashMap::new(),
        };

        // When: Merging OpenLibrary data
        merge_openlibrary_data(&mut book, ol_response);

        // Then: Book should remain unchanged
        assert_eq!(book.title, "Test");
        assert!(book.publisher.is_none());
    }

    // Note: Full integration tests with actual OpenLibraryClient would go in
    // tests/book_identifier_test.rs and should use mock HTTP servers
}
