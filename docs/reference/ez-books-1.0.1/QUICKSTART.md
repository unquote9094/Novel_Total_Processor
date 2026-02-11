# EZ-Books Quick Start Guide

Get up and running with EZ-Books in 5 minutes!

## Prerequisites

Make sure you have:
- Rust 1.65+ installed (`rustc --version`)
- Git (to clone the repository)

## Installation

### 1. Clone and Build

```bash
# Clone the repository
git clone <repository-url>
cd ez-books

# Build the release binary (takes 3-5 minutes)
cargo build --release
```

The compiled binary will be at `target/release/ez-books` (13MB)

### 2. Start the Server

```bash
# Run the server
cargo run --release
```

You should see:
```
INFO ez_books: EZ-Books starting...
INFO ez_books: Configuration loaded host=127.0.0.1 port=8080
INFO ez_books: Database initialized successfully
INFO ez_books: File storage initialized successfully
INFO ez_books: OpenLibrary client initialized successfully
INFO ez_books: EZ-Books is ready! Open http://127.0.0.1:8080 in your browser
```

### 3. Open in Browser

Navigate to: **http://127.0.0.1:8080**

## First Steps

### Upload Your First Book

1. Click the **"Choose File"** button
2. Select an EPUB file from your computer
3. Click **"Upload EPUB"**
4. Wait for processing (usually 2-5 seconds)
5. Your book appears in the gallery!

### Read a Book

1. Click the **"Read"** button on any book card
2. Enjoy the clean, distraction-free reading experience
3. Use browser back button to return to library

### Delete a Book

1. Click the **"Delete"** button on any book card
2. Confirm the deletion in the dialog
3. Book is removed from library and storage

## What Happens During Upload?

When you upload an EPUB, EZ-Books automatically:

1. ✅ Extracts metadata (title, author, ISBN, etc.)
2. ✅ Searches OpenLibrary for additional information
3. ✅ Extracts and resizes the cover image
4. ✅ Stores the book in SQLite database
5. ✅ Saves files to disk storage

## Directory Structure

After first run, you'll have:

```
ez-books/
├── data/
│   ├── ez-books.db        # SQLite database
│   ├── books/             # EPUB files
│   │   └── {uuid}.epub
│   └── covers/            # Cover images
│       └── {uuid}.jpg
└── target/release/
    └── ez-books           # Compiled binary
```

## Configuration

### Change Port

```bash
export SERVER_PORT=3000
cargo run --release
```

### Change Data Directory

```bash
export STORAGE_PATH=/path/to/storage
cargo run --release
```

### Using .env File

```bash
# Copy example configuration
cp .env.example .env

# Edit configuration
nano .env  # or your preferred editor

# Run server (automatically loads .env)
cargo run --release
```

## Testing the API

### List All Books (JSON)

```bash
curl http://localhost:8080/api/books
```

### Get Book Details

```bash
curl http://localhost:8080/api/books/{book-id}
```

### Delete a Book

```bash
curl -X DELETE http://localhost:8080/api/books/{book-id}
```

## Common Issues

### Port Already in Use

```bash
# Find what's using port 8080
lsof -i :8080

# Use different port
export SERVER_PORT=3000
cargo run --release
```

### Permission Denied

```bash
# Make sure data directory is writable
chmod 755 data/
chmod 755 data/books/
chmod 755 data/covers/
```

### Compilation Errors

```bash
# Update Rust to latest version
rustup update

# Clean build cache
cargo clean

# Rebuild
cargo build --release
```

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Check the API documentation for integration
- Explore the configuration options
- Set up a reverse proxy for production use

## Getting Help

- **Check logs**: Server outputs detailed logs
- **Test with sample EPUB**: Try a public domain book first
- **Verify network**: OpenLibrary enrichment requires internet
- **Check file size**: Default limit is 50MB per EPUB

## Production Deployment

For production use:

1. Build with optimizations (already done with `--release`)
2. Run behind reverse proxy (nginx/Caddy)
3. Use HTTPS for security
4. Set up automatic backups of `data/` directory
5. Monitor disk space for uploads
6. Consider using systemd service for auto-restart

### Example systemd Service

```ini
[Unit]
Description=EZ-Books EPUB Manager
After=network.target

[Service]
Type=simple
User=ezbooks
WorkingDirectory=/opt/ez-books
Environment="SERVER_HOST=127.0.0.1"
Environment="SERVER_PORT=8080"
ExecStart=/opt/ez-books/target/release/ez-books
Restart=always

[Install]
WantedBy=multi-user.target
```

---

**Enjoy your personal ebook library!** 📚
