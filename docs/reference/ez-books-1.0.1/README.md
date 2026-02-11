# EZ-Books

A simple, self-hosted EPUB ebook manager with automatic metadata enrichment from OpenLibrary.

## Features

- 📚 **EPUB Management** - Upload, store, and organize your EPUB ebooks
- 🎨 **Beautiful Gallery** - Responsive grid layout with book covers
- 📖 **Built-in Reader** - JavaScript-free reading experience
- 🌐 **Metadata Enrichment** - Automatic book information from OpenLibrary
- 🔍 **ISBN Detection** - Smart ISBN extraction from EPUB files
- 🖼️ **Cover Extraction** - Automatic cover image processing
- 🔒 **Security First** - HTML sanitization, XSS protection
- 💾 **Single Binary** - All static assets embedded
- 🚀 **Fast & Efficient** - Rust-powered backend

## Quick Start

### Prerequisites

- Rust 1.65 or later
- SQLite 3

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd ez-books

# Build the project
cargo build --release

# Run the server
cargo run --release
```

The server will start on `http://127.0.0.1:8080`

## Usage

### Upload Books

1. Open your browser to `http://127.0.0.1:8080`
2. Click "Choose File" and select an EPUB file
3. Click "Upload EPUB"
4. The book will be automatically:
   - Parsed for metadata
   - Enriched with OpenLibrary data (if ISBN found)
   - Cover extracted and resized
   - Added to your library

### Read Books

1. Click "Read" on any book card in the gallery
2. Enjoy the clean, distraction-free reading experience
3. Use browser back button to return to library

### Delete Books

1. Click "Delete" on any book card
2. Confirm the deletion
3. Book and associated files are removed

## Configuration

Configuration is done via environment variables:

```bash
# Server settings
export SERVER_HOST=127.0.0.1
export SERVER_PORT=8080

# Database
export DATABASE_URL=sqlite://data/ez-books.db

# Storage
export STORAGE_PATH=./data

# OpenLibrary API
export OPENLIBRARY_API_URL=https://openlibrary.org

# Upload limits (bytes)
export MAX_UPLOAD_SIZE=52428800  # 50MB
```

See `.env.example` for a complete configuration template.

## API Endpoints

### REST API

```
GET  /api/books        List all books (JSON)
GET  /api/books/:id    Get book details (JSON)
DELETE /api/books/:id  Delete a book
POST /upload           Upload EPUB file
```

### Web Routes

```
GET  /                 Gallery page
GET  /reader/:id       Reader page
GET  /covers/:id       Cover image (JPEG)
GET  /static/*         Static assets
```

## Architecture

### Technology Stack

- **Backend**: Rust with Warp web framework
- **Database**: SQLite with sqlx (compile-time checked queries)
- **EPUB**: epub crate for parsing
- **HTTP Client**: reqwest with RustTLS
- **Frontend**: Plain HTML, CSS, JavaScript (progressive enhancement)
- **Logging**: tracing and tracing-subscriber

### Project Structure

```
ez-books/
├── src/
│   ├── main.rs                  # Server entry point
│   ├── config.rs                # Configuration
│   ├── error.rs                 # Error types
│   ├── book_model.rs            # Data model
│   ├── book_repository.rs       # Database operations
│   ├── database_connection.rs   # SQLite pool
│   ├── file_storage.rs          # File operations
│   ├── epub_parser.rs           # EPUB metadata
│   ├── epub_cover_extractor.rs  # Cover processing
│   ├── openlibrary_client.rs    # API client
│   ├── openlibrary_types.rs     # API types
│   ├── book_identifier.rs       # Metadata enrichment
│   ├── html_templates.rs        # HTML helpers
│   ├── gallery_renderer.rs      # Gallery HTML
│   ├── reader_renderer.rs       # Reader HTML
│   ├── upload_handler.rs        # Upload workflow
│   ├── route_handlers.rs        # HTTP handlers
│   ├── route_filters.rs         # Routing
│   └── static_assets.rs         # Embedded assets
├── static/
│   ├── css/
│   │   ├── gallery.css          # Gallery styles
│   │   └── reader.css           # Reader styles
│   └── js/
│       └── upload.js            # Upload logic
├── migrations/
│   └── 001_initial_schema.sql   # Database schema
└── tests/                       # Unit tests
```

### Database Schema

```sql
-- Books table
CREATE TABLE books (
    id TEXT PRIMARY KEY,           -- UUID
    title TEXT NOT NULL,
    author TEXT,
    isbn_10 TEXT,
    isbn_13 TEXT,
    publisher TEXT,
    publish_date TEXT,
    description TEXT,
    cover_image_path TEXT,
    epub_file_path TEXT NOT NULL,
    openlibrary_key TEXT,
    openlibrary_work_key TEXT,
    page_count INTEGER,
    language TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

-- Book subjects (many-to-many)
CREATE TABLE book_subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id TEXT NOT NULL,
    subject TEXT NOT NULL,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
);
```

## Development

### Running Tests

```bash
# Run all tests
cargo test

# Run tests with output
cargo test -- --nocapture

# Run specific test
cargo test test_name
```

### Code Quality

```bash
# Format code
cargo fmt

# Run linter
cargo clippy

# Check without building
cargo check
```

### Test Coverage

- 92 unit tests covering all modules
- BDD-style tests (Given-When-Then)
- Integration tests for complete workflows
- 100% coverage of critical paths

## Security

### Implemented Protections

- **HTML Sanitization**: All EPUB content sanitized with ammonia
- **XSS Prevention**: HTML escaping for all user input
- **File Validation**: MIME type and extension checking
- **Size Limits**: Configurable upload size limits
- **SQL Injection**: Compile-time checked queries with sqlx
- **Path Traversal**: Sanitized file paths
- **Error Handling**: No sensitive data in error messages

### Recommendations

1. Run behind a reverse proxy (nginx, Caddy)
2. Use HTTPS in production
3. Set appropriate file permissions on data directory
4. Regular database backups
5. Monitor disk space for uploads

## Performance

### Optimizations

- Static assets embedded in binary (zero disk I/O)
- Database connection pooling
- Efficient EPUB parsing (streaming)
- Image resizing with Lanczos3 filter
- HTTP caching headers for static assets
- Compile-time SQL verification

### Resource Usage

- **Memory**: ~10-20MB idle, scales with uploads
- **CPU**: Minimal, spikes during EPUB processing
- **Disk**: EPUB files + covers + small SQLite DB
- **Network**: Only for OpenLibrary API calls

## Troubleshooting

### Server won't start

```bash
# Check if port is already in use
lsof -i :8080

# Try different port
export SERVER_PORT=3000
cargo run --release
```

### Database errors

```bash
# Delete and recreate database
rm -rf data/
mkdir -p data/books data/covers
cargo run --release
```

### Upload fails

- Check file is valid EPUB
- Verify file size < MAX_UPLOAD_SIZE
- Check disk space available
- Review server logs for errors

### OpenLibrary enrichment not working

- Check internet connectivity
- Verify OPENLIBRARY_API_URL is correct
- Books without ISBNs won't be enriched
- API may be rate-limited (graceful fallback)

## Roadmap

Potential future enhancements:

- [ ] Full-text search across books
- [ ] Collections/shelves organization
- [ ] Reading progress tracking
- [ ] Export/import library
- [ ] Multiple user support
- [ ] Book recommendations
- [ ] OPDS catalog support
- [ ] Mobile-responsive reader improvements
- [ ] Dark mode
- [ ] Bookmarks and annotations

## Contributing

Contributions welcome! Please follow these guidelines:

1. Write tests for new features
2. Follow existing code style
3. Run `cargo fmt` and `cargo clippy`
4. Update documentation
5. Keep commits atomic and well-described

## License

[Your chosen license]

## Acknowledgments

- [epub crate](https://crates.io/crates/epub) for EPUB parsing
- [OpenLibrary](https://openlibrary.org/) for metadata
- [Warp](https://github.com/seanmonstar/warp) for web framework
- [sqlx](https://github.com/launchbadge/sqlx) for database access

## Support

For issues and questions:
- Open an issue on GitHub
- Check existing documentation
- Review server logs for errors

---

Built with ❤️ using Rust
