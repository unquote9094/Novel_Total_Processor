use thiserror::Error;

#[derive(Error, Debug)]
pub enum EzBooksError {
    #[error("Database error: {0}")]
    Database(#[from] sqlx::Error),

    #[error("EPUB parsing error: {0}")]
    EpubParse(String),

    #[error("OpenLibrary API error: {0}")]
    OpenLibraryApi(String),

    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("Book not found: {0}")]
    BookNotFound(String),

    #[error("Invalid file format")]
    InvalidFormat,

    #[error("File storage error: {0}")]
    FileStorage(String),

    #[error("Image processing error: {0}")]
    ImageProcessing(String),

    #[error("HTTP request error: {0}")]
    HttpRequest(#[from] reqwest::Error),

    #[error("JSON serialization error: {0}")]
    JsonSerialization(#[from] serde_json::Error),
}

pub type Result<T> = std::result::Result<T, EzBooksError>;

// Convert to warp rejections for HTTP responses
impl warp::reject::Reject for EzBooksError {}
