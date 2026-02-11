use crate::error::{EzBooksError, Result};
use crate::openlibrary_types::BooksApiResponse;
use reqwest::Client;
use std::time::Duration;
use tracing::{info, instrument, warn};

const DEFAULT_BASE_URL: &str = "https://openlibrary.org";
const REQUEST_TIMEOUT: Duration = Duration::from_secs(30);

#[derive(Clone, Debug)]
pub struct OpenLibraryClient {
    http_client: Client,
    base_url: String,
}

impl OpenLibraryClient {
    pub fn new() -> Result<Self> {
        Self::with_base_url(DEFAULT_BASE_URL)
    }

    pub fn with_base_url(base_url: &str) -> Result<Self> {
        let http_client = Client::builder()
            .timeout(REQUEST_TIMEOUT)
            .user_agent("ez-books/0.1.0")
            .build()
            .map_err(|e| {
                EzBooksError::OpenLibraryApi(format!("Failed to create HTTP client: {}", e))
            })?;

        Ok(Self {
            http_client,
            base_url: base_url.to_string(),
        })
    }

    #[instrument(skip(self))]
    pub async fn lookup_by_isbn(&self, isbn: &str) -> Result<Option<BooksApiResponse>> {
        info!(isbn = %isbn, "Looking up book by ISBN on OpenLibrary");

        let url = format!(
            "{}/api/books?bibkeys=ISBN:{}&format=json&jscmd=data",
            self.base_url, isbn
        );

        let response = self.http_client.get(&url).send().await.map_err(|e| {
            warn!(isbn = %isbn, error = %e, "Failed to send request to OpenLibrary");
            EzBooksError::OpenLibraryApi(format!("Request failed: {}", e))
        })?;

        if !response.status().is_success() {
            warn!(
                isbn = %isbn,
                status = %response.status(),
                "OpenLibrary returned non-success status"
            );
            return Err(EzBooksError::OpenLibraryApi(format!(
                "API returned status: {}",
                response.status()
            )));
        }

        let response_text = response.text().await.map_err(|e| {
            warn!(isbn = %isbn, error = %e, "Failed to read response body");
            EzBooksError::OpenLibraryApi(format!("Failed to read response: {}", e))
        })?;

        // OpenLibrary returns empty object {} when no book is found
        if response_text.trim() == "{}" {
            info!(isbn = %isbn, "No book found on OpenLibrary");
            return Ok(None);
        }

        let books_response: BooksApiResponse =
            serde_json::from_str(&response_text).map_err(|e| {
                warn!(
                    isbn = %isbn,
                    error = %e,
                    response = %response_text,
                    "Failed to parse OpenLibrary response"
                );
                EzBooksError::OpenLibraryApi(format!("Failed to parse response: {}", e))
            })?;

        if books_response.books.is_empty() {
            info!(isbn = %isbn, "No book found in OpenLibrary response");
            Ok(None)
        } else {
            info!(isbn = %isbn, "Successfully retrieved book data from OpenLibrary");
            Ok(Some(books_response))
        }
    }
}

impl Default for OpenLibraryClient {
    fn default() -> Self {
        Self::new().expect("Failed to create default OpenLibraryClient")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn should_create_client_with_default_base_url() {
        // Given/When: Creating a default client
        let result = OpenLibraryClient::new();

        // Then: Should succeed
        assert!(result.is_ok());
        let client = result.unwrap();
        assert_eq!(client.base_url, DEFAULT_BASE_URL);
    }

    #[test]
    fn should_create_client_with_custom_base_url() {
        // Given: A custom base URL
        let custom_url = "https://test.example.com";

        // When: Creating a client with custom URL
        let result = OpenLibraryClient::with_base_url(custom_url);

        // Then: Should succeed with custom URL
        assert!(result.is_ok());
        let client = result.unwrap();
        assert_eq!(client.base_url, custom_url);
    }

    #[test]
    fn should_construct_correct_api_url() {
        // Given: A client
        let client = OpenLibraryClient::new().unwrap();
        let isbn = "9780140328721";

        // When: Constructing the API URL
        let url = format!(
            "{}/api/books?bibkeys=ISBN:{}&format=json&jscmd=data",
            client.base_url, isbn
        );

        // Then: URL should be correctly formatted
        assert!(url.contains("/api/books"));
        assert!(url.contains("bibkeys=ISBN:9780140328721"));
        assert!(url.contains("format=json"));
        assert!(url.contains("jscmd=data"));
    }

    // Note: Integration tests that make actual API calls would go in
    // tests/openlibrary_client_test.rs and should be marked with #[ignore]
    // to avoid hitting the real API during normal test runs
}
