use crate::database_connection::DatabasePool;
use crate::file_storage::FileStorage;
use crate::openlibrary_client::OpenLibraryClient;
use crate::route_handlers::*;
use crate::static_assets::serve_static;
use warp::{Filter, Rejection, Reply};

pub fn routes(
    pool: DatabasePool,
    storage: FileStorage,
    ol_client: OpenLibraryClient,
) -> impl Filter<Extract = impl Reply, Error = Rejection> + Clone {
    gallery_route(pool.clone())
        .or(static_route())
        .or(api_books_route(pool.clone()))
        .or(api_book_detail_route(pool.clone()))
        .or(cover_route(storage.clone()))
        .or(reader_route(pool.clone(), storage.clone()))
        .or(upload_route(pool.clone(), storage.clone(), ol_client))
        .or(delete_route(pool, storage))
}

fn gallery_route(
    pool: DatabasePool,
) -> impl Filter<Extract = impl Reply, Error = Rejection> + Clone {
    warp::path::end()
        .and(warp::get())
        .and(with_db(pool))
        .and_then(handle_gallery)
}

fn static_route() -> impl Filter<Extract = impl Reply, Error = Rejection> + Clone {
    serve_static()
}

fn api_books_route(
    pool: DatabasePool,
) -> impl Filter<Extract = impl Reply, Error = Rejection> + Clone {
    warp::path!("api" / "books")
        .and(warp::get())
        .and(with_db(pool))
        .and_then(handle_api_books)
}

fn api_book_detail_route(
    pool: DatabasePool,
) -> impl Filter<Extract = impl Reply, Error = Rejection> + Clone {
    warp::path!("api" / "books" / String)
        .and(warp::get())
        .and(with_db(pool))
        .and_then(handle_api_book_detail)
}

fn cover_route(
    storage: FileStorage,
) -> impl Filter<Extract = impl Reply, Error = Rejection> + Clone {
    warp::path!("covers" / String)
        .and(warp::get())
        .and(with_storage(storage))
        .and_then(handle_cover)
}

fn reader_route(
    pool: DatabasePool,
    storage: FileStorage,
) -> impl Filter<Extract = impl Reply, Error = Rejection> + Clone {
    warp::path!("reader" / String)
        .and(warp::get())
        .and(with_db(pool))
        .and(with_storage(storage))
        .and_then(handle_reader)
}

fn upload_route(
    pool: DatabasePool,
    storage: FileStorage,
    ol_client: OpenLibraryClient,
) -> impl Filter<Extract = impl Reply, Error = Rejection> + Clone {
    warp::path("upload")
        .and(warp::post())
        .and(warp::multipart::form().max_length(52_428_800)) // 50MB max
        .and(with_db(pool))
        .and(with_storage(storage))
        .and(with_ol_client(ol_client))
        .and_then(handle_upload)
}

fn delete_route(
    pool: DatabasePool,
    storage: FileStorage,
) -> impl Filter<Extract = impl Reply, Error = Rejection> + Clone {
    warp::path!("api" / "books" / String)
        .and(warp::delete())
        .and(with_db(pool))
        .and(with_storage(storage))
        .and_then(handle_delete)
}

fn with_db(
    pool: DatabasePool,
) -> impl Filter<Extract = (DatabasePool,), Error = std::convert::Infallible> + Clone {
    warp::any().map(move || pool.clone())
}

fn with_storage(
    storage: FileStorage,
) -> impl Filter<Extract = (FileStorage,), Error = std::convert::Infallible> + Clone {
    warp::any().map(move || storage.clone())
}

fn with_ol_client(
    client: OpenLibraryClient,
) -> impl Filter<Extract = (OpenLibraryClient,), Error = std::convert::Infallible> + Clone {
    warp::any().map(move || client.clone())
}
