use crate::book_repository;
use crate::database_connection::DatabasePool;
use crate::error::EzBooksError;
use crate::file_storage::FileStorage;
use crate::gallery_renderer::render_gallery;
use crate::openlibrary_client::OpenLibraryClient;
use crate::reader_renderer::{extract_and_sanitize_content, render_reader};
use crate::upload_handler::process_upload;
use bytes::BufMut;
use futures::TryStreamExt;
use tracing::{info, instrument, warn};
use warp::http::StatusCode;
use warp::multipart::{FormData, Part};
use warp::{reject, Rejection, Reply};

#[instrument(skip(pool))]
pub async fn handle_gallery(pool: DatabasePool) -> Result<impl Reply, Rejection> {
    info!("Handling gallery request");

    let books = book_repository::find_all(&pool).await.map_err(|e| {
        warn!(error = %e, "Failed to fetch books");
        reject::custom(e)
    })?;

    let html = render_gallery(books);

    Ok(warp::reply::html(html))
}

#[instrument(skip(pool))]
pub async fn handle_api_books(pool: DatabasePool) -> Result<impl Reply, Rejection> {
    info!("Handling API books list request");

    let books = book_repository::find_all(&pool).await.map_err(|e| {
        warn!(error = %e, "Failed to fetch books");
        reject::custom(e)
    })?;

    Ok(warp::reply::json(&books))
}

#[instrument(skip(pool))]
pub async fn handle_api_book_detail(
    id: String,
    pool: DatabasePool,
) -> Result<impl Reply, Rejection> {
    info!(book_id = %id, "Handling API book detail request");

    let book = book_repository::find_by_id(&pool, &id).await.map_err(|e| {
        warn!(book_id = %id, error = %e, "Failed to fetch book");
        reject::custom(e)
    })?;

    Ok(warp::reply::json(&book))
}

#[instrument(skip(storage))]
pub async fn handle_cover(id: String, storage: FileStorage) -> Result<impl Reply, Rejection> {
    info!(book_id = %id, "Handling cover image request");

    let cover_data = storage.read_cover(&id).map_err(|e| {
        warn!(book_id = %id, error = %e, "Failed to read cover");
        reject::custom(e)
    })?;

    Ok(warp::reply::with_header(
        cover_data,
        "content-type",
        "image/jpeg",
    ))
}

#[instrument(skip(pool, storage))]
pub async fn handle_reader(
    id: String,
    pool: DatabasePool,
    storage: FileStorage,
) -> Result<impl Reply, Rejection> {
    info!(book_id = %id, "Handling reader request");

    let book = book_repository::find_by_id(&pool, &id).await.map_err(|e| {
        warn!(book_id = %id, error = %e, "Failed to fetch book");
        reject::custom(e)
    })?;

    let epub_data = storage.read_epub(&id).map_err(|e| {
        warn!(book_id = %id, error = %e, "Failed to read EPUB");
        reject::custom(e)
    })?;

    // Save to temp file for reading
    let temp_path = std::env::temp_dir().join(format!("{}.epub", id));
    std::fs::write(&temp_path, epub_data).map_err(|e| {
        warn!(error = %e, "Failed to write temp file");
        reject::custom(EzBooksError::Io(e))
    })?;

    let content = extract_and_sanitize_content(&temp_path).map_err(|e| {
        warn!(book_id = %id, error = %e, "Failed to extract content");
        reject::custom(e)
    })?;

    // Clean up temp file
    let _ = std::fs::remove_file(&temp_path);

    let html = render_reader(&book, content);

    Ok(warp::reply::html(html))
}

#[instrument(skip(form, pool, storage, ol_client))]
pub async fn handle_upload(
    form: FormData,
    pool: DatabasePool,
    storage: FileStorage,
    ol_client: OpenLibraryClient,
) -> Result<impl Reply, Rejection> {
    info!("Handling upload request");

    let parts: Vec<Part> = form.try_collect().await.map_err(|e| {
        warn!(error = %e, "Failed to collect form parts");
        reject::reject()
    })?;

    for part in parts {
        if part.name() == "file" {
            let filename = part.filename().unwrap_or("unknown.epub").to_string();

            if !filename.to_lowercase().ends_with(".epub") {
                return Err(reject::custom(EzBooksError::InvalidFormat));
            }

            let data = part
                .stream()
                .try_fold(Vec::new(), |mut vec, data| {
                    vec.put(data);
                    async move { Ok(vec) }
                })
                .await
                .map_err(|e| {
                    warn!(error = %e, "Failed to read file data");
                    reject::reject()
                })?;

            let response = process_upload(filename, data, pool, storage, ol_client)
                .await
                .map_err(|e| {
                    warn!(error = %e, "Failed to process upload");
                    reject::custom(e)
                })?;

            return Ok(warp::reply::with_status(
                warp::reply::json(&response),
                StatusCode::OK,
            ));
        }
    }

    Err(reject::custom(EzBooksError::InvalidFormat))
}

#[instrument(skip(pool, storage))]
pub async fn handle_delete(
    id: String,
    pool: DatabasePool,
    storage: FileStorage,
) -> Result<impl Reply, Rejection> {
    info!(book_id = %id, "Handling delete request");

    // Delete from database
    book_repository::delete(&pool, &id).await.map_err(|e| {
        warn!(book_id = %id, error = %e, "Failed to delete book from database");
        reject::custom(e)
    })?;

    // Delete files from storage
    let _ = storage.delete_epub(&id);
    let _ = storage.delete_cover(&id);

    Ok(warp::reply::with_status(
        warp::reply::json(&serde_json::json!({"success": true})),
        StatusCode::OK,
    ))
}
