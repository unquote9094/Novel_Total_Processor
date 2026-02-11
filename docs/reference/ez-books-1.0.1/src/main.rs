mod book_identifier;
mod book_model;
mod book_repository;
mod config;
mod database_connection;
mod epub_cover_extractor;
mod epub_parser;
mod error;
mod file_storage;
mod gallery_renderer;
mod html_templates;
mod openlibrary_client;
mod openlibrary_types;
mod reader_renderer;
mod route_filters;
mod route_handlers;
mod static_assets;
mod upload_handler;

use config::Config;
use database_connection::{create_pool, run_migrations};
use file_storage::FileStorage;
use openlibrary_client::OpenLibraryClient;
use route_filters::routes;
use tracing_subscriber::fmt::format::FmtSpan;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize tracing
    tracing_subscriber::fmt()
        .with_env_filter("ez_books=info,warn,error")
        .with_span_events(FmtSpan::CLOSE)
        .init();

    tracing::info!("EZ-Books starting...");

    // Load configuration
    let config = Config::from_env()?;
    tracing::info!(
        host = %config.server_host,
        port = config.server_port,
        "Configuration loaded"
    );

    // Initialize database
    tracing::info!("Initializing database...");
    let pool = create_pool(&config.database_url).await?;
    run_migrations(&pool).await?;
    tracing::info!("Database initialized successfully");

    // Initialize file storage
    tracing::info!(path = %config.storage_path, "Initializing file storage...");
    let storage = FileStorage::new(&config.storage_path)?;
    tracing::info!("File storage initialized successfully");

    // Initialize OpenLibrary client
    tracing::info!("Initializing OpenLibrary client...");
    let ol_client = OpenLibraryClient::with_base_url(&config.openlibrary_api_url)?;
    tracing::info!("OpenLibrary client initialized successfully");

    // Build routes
    let routes = routes(pool, storage, ol_client);

    // Start server
    let addr: std::net::SocketAddr = config.server_address().parse()?;
    tracing::info!(address = %addr, "Starting web server...");
    tracing::info!("EZ-Books is ready! Open http://{} in your browser", addr);

    warp::serve(routes).run(addr).await;

    Ok(())
}
