use serde::{Deserialize, Serialize};

/// Response from OpenLibrary Books API
/// https://openlibrary.org/dev/docs/api/books
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BooksApiResponse {
    #[serde(flatten)]
    pub books: std::collections::HashMap<String, BookData>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BookData {
    #[serde(default)]
    pub title: Option<String>,

    #[serde(default)]
    pub subtitle: Option<String>,

    #[serde(default)]
    pub authors: Vec<Author>,

    #[serde(default)]
    pub publishers: Vec<Publisher>,

    #[serde(default)]
    pub publish_date: Option<String>,

    #[serde(default)]
    pub number_of_pages: Option<i32>,

    #[serde(default)]
    pub identifiers: Option<Identifiers>,

    #[serde(default)]
    pub subjects: Vec<Subject>,

    #[serde(default)]
    pub cover: Option<Cover>,

    #[serde(default)]
    pub url: Option<String>,

    #[serde(default)]
    pub key: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Author {
    pub name: String,

    #[serde(default)]
    pub url: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Publisher {
    pub name: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Identifiers {
    #[serde(default)]
    pub isbn_10: Option<Vec<String>>,

    #[serde(default)]
    pub isbn_13: Option<Vec<String>>,

    #[serde(default)]
    pub openlibrary: Option<Vec<String>>,

    #[serde(default)]
    pub goodreads: Option<Vec<String>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Subject {
    pub name: String,

    #[serde(default)]
    pub url: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Cover {
    #[serde(default)]
    pub small: Option<String>,

    #[serde(default)]
    pub medium: Option<String>,

    #[serde(default)]
    pub large: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn should_deserialize_books_api_response() {
        // Given: A sample Books API response
        let json = r#"{
            "ISBN:9780140328721": {
                "title": "Fantastic Mr. Fox",
                "authors": [
                    {"name": "Roald Dahl"}
                ],
                "publishers": [
                    {"name": "Puffin"}
                ],
                "publish_date": "1988",
                "number_of_pages": 96,
                "identifiers": {
                    "isbn_13": ["9780140328721"],
                    "isbn_10": ["0140328726"]
                },
                "cover": {
                    "small": "https://covers.openlibrary.org/b/id/108626-S.jpg",
                    "medium": "https://covers.openlibrary.org/b/id/108626-M.jpg",
                    "large": "https://covers.openlibrary.org/b/id/108626-L.jpg"
                }
            }
        }"#;

        // When: Deserializing the response
        let result: Result<BooksApiResponse, _> = serde_json::from_str(json);

        // Then: Should succeed
        assert!(result.is_ok());
        let response = result.unwrap();

        // And: Should contain the book data
        assert_eq!(response.books.len(), 1);
        let book_data = response.books.get("ISBN:9780140328721").unwrap();
        assert_eq!(book_data.title, Some("Fantastic Mr. Fox".to_string()));
        assert_eq!(book_data.authors.len(), 1);
        assert_eq!(book_data.authors[0].name, "Roald Dahl");
        assert_eq!(book_data.publishers.len(), 1);
        assert_eq!(book_data.publishers[0].name, "Puffin");
        assert_eq!(book_data.number_of_pages, Some(96));
    }

    #[test]
    fn should_handle_missing_optional_fields() {
        // Given: A minimal Books API response
        let json = r#"{
            "ISBN:1234567890": {
                "title": "Test Book"
            }
        }"#;

        // When: Deserializing the response
        let result: Result<BooksApiResponse, _> = serde_json::from_str(json);

        // Then: Should succeed with default values for optional fields
        assert!(result.is_ok());
        let response = result.unwrap();
        let book_data = response.books.get("ISBN:1234567890").unwrap();
        assert_eq!(book_data.title, Some("Test Book".to_string()));
        assert!(book_data.authors.is_empty());
        assert!(book_data.publishers.is_empty());
        assert!(book_data.identifiers.is_none());
    }

    #[test]
    fn should_deserialize_array_fields() {
        // Given: A response with multiple authors and subjects
        let json = r#"{
            "ISBN:1234567890": {
                "title": "Test Book",
                "authors": [
                    {"name": "Author One"},
                    {"name": "Author Two"}
                ],
                "subjects": [
                    {"name": "Fiction"},
                    {"name": "Adventure"}
                ]
            }
        }"#;

        // When: Deserializing the response
        let result: Result<BooksApiResponse, _> = serde_json::from_str(json);

        // Then: Should parse all array elements
        assert!(result.is_ok());
        let response = result.unwrap();
        let book_data = response.books.get("ISBN:1234567890").unwrap();
        assert_eq!(book_data.authors.len(), 2);
        assert_eq!(book_data.authors[0].name, "Author One");
        assert_eq!(book_data.authors[1].name, "Author Two");
        assert_eq!(book_data.subjects.len(), 2);
        assert_eq!(book_data.subjects[0].name, "Fiction");
        assert_eq!(book_data.subjects[1].name, "Adventure");
    }
}
