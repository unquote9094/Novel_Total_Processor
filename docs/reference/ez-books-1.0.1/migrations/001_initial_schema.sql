-- Books table
CREATE TABLE IF NOT EXISTS books (
    id TEXT PRIMARY KEY NOT NULL,
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

-- Indexes for search performance
CREATE INDEX IF NOT EXISTS idx_books_title ON books(title);
CREATE INDEX IF NOT EXISTS idx_books_author ON books(author);
CREATE INDEX IF NOT EXISTS idx_books_isbn_10 ON books(isbn_10);
CREATE INDEX IF NOT EXISTS idx_books_isbn_13 ON books(isbn_13);
CREATE INDEX IF NOT EXISTS idx_books_created_at ON books(created_at);

-- Book subjects/genres (many-to-many)
CREATE TABLE IF NOT EXISTS book_subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id TEXT NOT NULL,
    subject TEXT NOT NULL,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    UNIQUE(book_id, subject)
);

CREATE INDEX IF NOT EXISTS idx_book_subjects_book_id ON book_subjects(book_id);
CREATE INDEX IF NOT EXISTS idx_book_subjects_subject ON book_subjects(subject);
