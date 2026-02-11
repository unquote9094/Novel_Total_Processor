use crate::error::{EzBooksError, Result};
use std::fs;
use std::path::{Path, PathBuf};
use tracing::{info, instrument, warn};

#[derive(Clone, Debug)]
pub struct FileStorage {
    base_path: PathBuf,
}

impl FileStorage {
    pub fn new(base_path: impl AsRef<Path>) -> Result<Self> {
        let base_path = base_path.as_ref().to_path_buf();

        // Create necessary directories
        let books_dir = base_path.join("books");
        let covers_dir = base_path.join("covers");

        fs::create_dir_all(&books_dir).map_err(|e| {
            EzBooksError::FileStorage(format!("Failed to create books directory: {}", e))
        })?;

        fs::create_dir_all(&covers_dir).map_err(|e| {
            EzBooksError::FileStorage(format!("Failed to create covers directory: {}", e))
        })?;

        info!(path = %base_path.display(), "File storage initialized");
        Ok(Self { base_path })
    }

    #[instrument(skip(self, data))]
    pub fn save_epub(&self, book_id: &str, data: &[u8]) -> Result<String> {
        let file_path = self.epub_path(book_id);
        info!(book_id = %book_id, path = %file_path.display(), "Saving EPUB file");

        fs::write(&file_path, data).map_err(|e| {
            warn!(book_id = %book_id, error = %e, "Failed to save EPUB file");
            EzBooksError::FileStorage(format!("Failed to save EPUB file: {}", e))
        })?;

        info!(book_id = %book_id, size = data.len(), "EPUB file saved successfully");
        Ok(file_path.to_string_lossy().to_string())
    }

    #[instrument(skip(self))]
    pub fn read_epub(&self, book_id: &str) -> Result<Vec<u8>> {
        let file_path = self.epub_path(book_id);
        info!(book_id = %book_id, path = %file_path.display(), "Reading EPUB file");

        let data = fs::read(&file_path).map_err(|e| {
            warn!(book_id = %book_id, error = %e, "Failed to read EPUB file");
            EzBooksError::FileStorage(format!("Failed to read EPUB file: {}", e))
        })?;

        info!(book_id = %book_id, size = data.len(), "EPUB file read successfully");
        Ok(data)
    }

    #[instrument(skip(self, data))]
    pub fn save_cover(&self, book_id: &str, data: &[u8]) -> Result<String> {
        let file_path = self.cover_path(book_id);
        info!(book_id = %book_id, path = %file_path.display(), "Saving cover image");

        fs::write(&file_path, data).map_err(|e| {
            warn!(book_id = %book_id, error = %e, "Failed to save cover image");
            EzBooksError::FileStorage(format!("Failed to save cover image: {}", e))
        })?;

        info!(book_id = %book_id, size = data.len(), "Cover image saved successfully");
        Ok(file_path.to_string_lossy().to_string())
    }

    #[instrument(skip(self))]
    pub fn read_cover(&self, book_id: &str) -> Result<Vec<u8>> {
        let file_path = self.cover_path(book_id);
        info!(book_id = %book_id, path = %file_path.display(), "Reading cover image");

        let data = fs::read(&file_path).map_err(|e| {
            warn!(book_id = %book_id, error = %e, "Failed to read cover image");
            EzBooksError::FileStorage(format!("Failed to read cover image: {}", e))
        })?;

        info!(book_id = %book_id, size = data.len(), "Cover image read successfully");
        Ok(data)
    }

    #[instrument(skip(self))]
    pub fn delete_epub(&self, book_id: &str) -> Result<()> {
        let file_path = self.epub_path(book_id);
        info!(book_id = %book_id, path = %file_path.display(), "Deleting EPUB file");

        if file_path.exists() {
            fs::remove_file(&file_path).map_err(|e| {
                warn!(book_id = %book_id, error = %e, "Failed to delete EPUB file");
                EzBooksError::FileStorage(format!("Failed to delete EPUB file: {}", e))
            })?;
            info!(book_id = %book_id, "EPUB file deleted successfully");
        } else {
            warn!(book_id = %book_id, "EPUB file not found for deletion");
        }

        Ok(())
    }

    #[instrument(skip(self))]
    pub fn delete_cover(&self, book_id: &str) -> Result<()> {
        let file_path = self.cover_path(book_id);
        info!(book_id = %book_id, path = %file_path.display(), "Deleting cover image");

        if file_path.exists() {
            fs::remove_file(&file_path).map_err(|e| {
                warn!(book_id = %book_id, error = %e, "Failed to delete cover image");
                EzBooksError::FileStorage(format!("Failed to delete cover image: {}", e))
            })?;
            info!(book_id = %book_id, "Cover image deleted successfully");
        } else {
            warn!(book_id = %book_id, "Cover image not found for deletion");
        }

        Ok(())
    }

    fn epub_path(&self, book_id: &str) -> PathBuf {
        self.base_path
            .join("books")
            .join(format!("{}.epub", book_id))
    }

    fn cover_path(&self, book_id: &str) -> PathBuf {
        self.base_path
            .join("covers")
            .join(format!("{}.jpg", book_id))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    fn create_test_storage() -> (FileStorage, TempDir) {
        let temp_dir = TempDir::new().unwrap();
        let storage = FileStorage::new(temp_dir.path()).unwrap();
        (storage, temp_dir)
    }

    #[test]
    fn should_create_storage_directories() {
        // Given: A temporary directory
        let temp_dir = TempDir::new().unwrap();

        // When: Creating file storage
        let result = FileStorage::new(temp_dir.path());

        // Then: Should succeed and create directories
        assert!(result.is_ok());
        assert!(temp_dir.path().join("books").exists());
        assert!(temp_dir.path().join("covers").exists());
    }

    #[test]
    fn should_save_and_read_epub() {
        // Given: A file storage
        let (storage, _temp_dir) = create_test_storage();
        let book_id = "test-book-id";
        let epub_data = b"This is test EPUB data";

        // When: Saving EPUB
        let save_result = storage.save_epub(book_id, epub_data);
        assert!(save_result.is_ok());

        // Then: Should be able to read it back
        let read_result = storage.read_epub(book_id);
        assert!(read_result.is_ok());
        assert_eq!(read_result.unwrap(), epub_data);
    }

    #[test]
    fn should_save_and_read_cover() {
        // Given: A file storage
        let (storage, _temp_dir) = create_test_storage();
        let book_id = "test-book-id";
        let cover_data = b"This is test cover data";

        // When: Saving cover
        let save_result = storage.save_cover(book_id, cover_data);
        assert!(save_result.is_ok());

        // Then: Should be able to read it back
        let read_result = storage.read_cover(book_id);
        assert!(read_result.is_ok());
        assert_eq!(read_result.unwrap(), cover_data);
    }

    #[test]
    fn should_return_error_when_reading_non_existent_epub() {
        // Given: A file storage
        let (storage, _temp_dir) = create_test_storage();

        // When: Reading non-existent EPUB
        let result = storage.read_epub("non-existent");

        // Then: Should return error
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), EzBooksError::FileStorage(_)));
    }

    #[test]
    fn should_return_error_when_reading_non_existent_cover() {
        // Given: A file storage
        let (storage, _temp_dir) = create_test_storage();

        // When: Reading non-existent cover
        let result = storage.read_cover("non-existent");

        // Then: Should return error
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), EzBooksError::FileStorage(_)));
    }

    #[test]
    fn should_delete_epub() {
        // Given: An EPUB file in storage
        let (storage, _temp_dir) = create_test_storage();
        let book_id = "test-book-id";
        storage.save_epub(book_id, b"test data").unwrap();
        assert!(storage.epub_path(book_id).exists());

        // When: Deleting the EPUB
        let result = storage.delete_epub(book_id);

        // Then: Should succeed and file should be removed
        assert!(result.is_ok());
        assert!(!storage.epub_path(book_id).exists());
    }

    #[test]
    fn should_delete_cover() {
        // Given: A cover image in storage
        let (storage, _temp_dir) = create_test_storage();
        let book_id = "test-book-id";
        storage.save_cover(book_id, b"test data").unwrap();
        assert!(storage.cover_path(book_id).exists());

        // When: Deleting the cover
        let result = storage.delete_cover(book_id);

        // Then: Should succeed and file should be removed
        assert!(result.is_ok());
        assert!(!storage.cover_path(book_id).exists());
    }

    #[test]
    fn should_handle_deleting_non_existent_epub_gracefully() {
        // Given: A file storage without any EPUBs
        let (storage, _temp_dir) = create_test_storage();

        // When: Deleting non-existent EPUB
        let result = storage.delete_epub("non-existent");

        // Then: Should succeed (idempotent)
        assert!(result.is_ok());
    }

    #[test]
    fn should_generate_correct_file_paths() {
        // Given: A file storage
        let (storage, _temp_dir) = create_test_storage();
        let book_id = "test-book-id";

        // When: Saving files
        let epub_path = storage.save_epub(book_id, b"epub").unwrap();
        let cover_path = storage.save_cover(book_id, b"cover").unwrap();

        // Then: Paths should be correct
        assert!(epub_path.contains("books"));
        assert!(epub_path.ends_with(".epub"));
        assert!(cover_path.contains("covers"));
        assert!(cover_path.ends_with(".jpg"));
    }
}
