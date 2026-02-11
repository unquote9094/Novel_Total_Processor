use crate::book_identifier::identify_and_enrich;
use crate::book_repository;
use crate::database_connection::DatabasePool;
use crate::epub_cover_extractor::extract_cover;
use crate::epub_parser::parse_epub;
use crate::error::Result;
use crate::file_storage::FileStorage;
use crate::openlibrary_client::OpenLibraryClient;
use serde::Serialize;
use std::path::PathBuf;
use tracing::{info, instrument, warn};

#[derive(Debug, Serialize)]
pub struct UploadResponse {
    pub id: String,
    pub title: String,
    pub author: Option<String>,
}

#[instrument(skip(file_data, pool, storage, ol_client))]
pub async fn process_upload(
    filename: String,
    file_data: Vec<u8>,
    pool: DatabasePool,
    storage: FileStorage,
    ol_client: OpenLibraryClient,
) -> Result<UploadResponse> {
    info!(filename = %filename, size = file_data.len(), "Processing EPUB upload");

    // Step 1: Save the EPUB file temporarily for processing
    let temp_path = save_temp_file(&filename, &file_data)?;

    // Step 2: Parse EPUB metadata
    info!("Parsing EPUB metadata");
    let epub_metadata = parse_epub(&temp_path)?;
    info!(title = %epub_metadata.title, "EPUB metadata parsed");

    // Step 3: Extract cover image
    info!("Extracting cover image");
    let cover_data = extract_cover(&temp_path)?;

    // Step 4: Identify and enrich with OpenLibrary
    info!("Identifying and enriching book metadata");
    let mut book = identify_and_enrich(&ol_client, epub_metadata, String::new()).await?;

    // Step 5: Save EPUB and cover to permanent storage
    let epub_path = storage.save_epub(&book.id, &file_data)?;
    book.epub_file_path = epub_path;

    if let Some(cover_bytes) = cover_data {
        let cover_path = storage.save_cover(&book.id, &cover_bytes)?;
        book.cover_image_path = Some(cover_path);
    }

    // Step 6: Save book to database
    book_repository::insert(&pool, &book).await?;

    // Step 7: Save subjects if any
    for subject in book_repository::find_subjects_by_book_id(&pool, &book.id).await? {
        book_repository::insert_subject(&pool, &book.id, &subject).await?;
    }

    // Clean up temp file
    if let Err(e) = std::fs::remove_file(&temp_path) {
        warn!(error = %e, "Failed to clean up temp file");
    }

    info!(book_id = %book.id, title = %book.title, "Upload processed successfully");

    Ok(UploadResponse {
        id: book.id,
        title: book.title,
        author: book.author,
    })
}

fn save_temp_file(filename: &str, data: &[u8]) -> Result<PathBuf> {
    use std::io::Write;

    let temp_dir = std::env::temp_dir();
    let temp_path = temp_dir.join(filename);

    let mut file = std::fs::File::create(&temp_path)?;
    file.write_all(data)?;

    Ok(temp_path)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn should_create_upload_response() {
        // Given: Book details
        let id = "test-id".to_string();
        let title = "Test Book".to_string();
        let author = Some("Test Author".to_string());

        // When: Creating upload response
        let response = UploadResponse {
            id: id.clone(),
            title: title.clone(),
            author: author.clone(),
        };

        // Then: Should have correct fields
        assert_eq!(response.id, id);
        assert_eq!(response.title, title);
        assert_eq!(response.author, author);
    }

    #[test]
    fn should_save_temp_file() {
        // Given: File data
        let filename = "test.epub";
        let data = b"test data";

        // When: Saving temp file
        let result = save_temp_file(filename, data);

        // Then: Should succeed and file should exist
        assert!(result.is_ok());
        let path = result.unwrap();
        assert!(path.exists());

        // Cleanup
        let _ = std::fs::remove_file(path);
    }

    #[test]
    fn should_serialize_upload_response_to_json() {
        // Given: An upload response
        let response = UploadResponse {
            id: "123".to_string(),
            title: "Test".to_string(),
            author: Some("Author".to_string()),
        };

        // When: Serializing to JSON
        let json = serde_json::to_string(&response);

        // Then: Should succeed
        assert!(json.is_ok());
        let json_str = json.unwrap();
        assert!(json_str.contains("\"id\":\"123\""));
        assert!(json_str.contains("\"title\":\"Test\""));
        assert!(json_str.contains("\"author\":\"Author\""));
    }
}
