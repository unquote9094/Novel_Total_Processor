use crate::book_model::Book;
use crate::database_connection::DatabasePool;
use crate::error::{EzBooksError, Result};
use sqlx::Row;
use tracing::{info, instrument, warn};

#[instrument(skip(pool, book))]
pub async fn insert(pool: &DatabasePool, book: &Book) -> Result<()> {
    info!(book_id = %book.id, title = %book.title, "Inserting book into database");

    sqlx::query(
        r#"
        INSERT INTO books (
            id, title, author, isbn_10, isbn_13, publisher, publish_date,
            description, cover_image_path, epub_file_path, openlibrary_key,
            openlibrary_work_key, page_count, language, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        "#,
    )
    .bind(&book.id)
    .bind(&book.title)
    .bind(&book.author)
    .bind(&book.isbn_10)
    .bind(&book.isbn_13)
    .bind(&book.publisher)
    .bind(&book.publish_date)
    .bind(&book.description)
    .bind(&book.cover_image_path)
    .bind(&book.epub_file_path)
    .bind(&book.openlibrary_key)
    .bind(&book.openlibrary_work_key)
    .bind(book.page_count)
    .bind(&book.language)
    .bind(book.created_at)
    .bind(book.updated_at)
    .execute(pool)
    .await?;

    info!(book_id = %book.id, "Book inserted successfully");
    Ok(())
}

#[instrument(skip(pool))]
pub async fn find_all(pool: &DatabasePool) -> Result<Vec<Book>> {
    info!("Fetching all books from database");

    let books = sqlx::query_as::<_, Book>("SELECT * FROM books ORDER BY created_at DESC")
        .fetch_all(pool)
        .await?;

    info!(count = books.len(), "Fetched all books");
    Ok(books)
}

#[instrument(skip(pool))]
pub async fn find_by_id(pool: &DatabasePool, id: &str) -> Result<Book> {
    info!(book_id = %id, "Fetching book by ID");

    let book = sqlx::query_as::<_, Book>("SELECT * FROM books WHERE id = ?")
        .bind(id)
        .fetch_optional(pool)
        .await?
        .ok_or_else(|| {
            warn!(book_id = %id, "Book not found");
            EzBooksError::BookNotFound(id.to_string())
        })?;

    info!(book_id = %id, title = %book.title, "Book found");
    Ok(book)
}

#[instrument(skip(pool))]
pub async fn delete(pool: &DatabasePool, id: &str) -> Result<()> {
    info!(book_id = %id, "Deleting book from database");

    let result = sqlx::query("DELETE FROM books WHERE id = ?")
        .bind(id)
        .execute(pool)
        .await?;

    if result.rows_affected() == 0 {
        warn!(book_id = %id, "Book not found for deletion");
        return Err(EzBooksError::BookNotFound(id.to_string()));
    }

    info!(book_id = %id, "Book deleted successfully");
    Ok(())
}

#[instrument(skip(pool))]
pub async fn insert_subject(pool: &DatabasePool, book_id: &str, subject: &str) -> Result<()> {
    info!(book_id = %book_id, subject = %subject, "Inserting book subject");

    sqlx::query("INSERT INTO book_subjects (book_id, subject) VALUES (?, ?)")
        .bind(book_id)
        .bind(subject)
        .execute(pool)
        .await?;

    info!(book_id = %book_id, subject = %subject, "Subject inserted successfully");
    Ok(())
}

#[instrument(skip(pool))]
pub async fn find_subjects_by_book_id(pool: &DatabasePool, book_id: &str) -> Result<Vec<String>> {
    info!(book_id = %book_id, "Fetching subjects for book");

    let subjects: Vec<String> = sqlx::query("SELECT subject FROM book_subjects WHERE book_id = ?")
        .bind(book_id)
        .fetch_all(pool)
        .await?
        .iter()
        .map(|row| row.get("subject"))
        .collect();

    info!(book_id = %book_id, count = subjects.len(), "Fetched subjects");
    Ok(subjects)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::database_connection::{create_pool, run_migrations};
    use tempfile::TempDir;

    async fn setup_test_db() -> (DatabasePool, TempDir) {
        let temp_dir = TempDir::new().unwrap();
        let db_path = temp_dir.path().join("test.db");
        let database_url = format!("sqlite://{}", db_path.display());

        let pool = create_pool(&database_url).await.unwrap();
        run_migrations(&pool).await.unwrap();

        (pool, temp_dir)
    }

    fn create_test_book() -> Book {
        Book::new("Test Book".to_string(), "/path/to/book.epub".to_string())
    }

    #[tokio::test]
    async fn should_insert_book_successfully() {
        // Given: A database and a book
        let (pool, _temp_dir) = setup_test_db().await;
        let book = create_test_book();

        // When: Inserting the book
        let result = insert(&pool, &book).await;

        // Then: Should succeed
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn should_find_book_by_id() {
        // Given: A book in the database
        let (pool, _temp_dir) = setup_test_db().await;
        let book = create_test_book();
        insert(&pool, &book).await.unwrap();

        // When: Finding the book by ID
        let result = find_by_id(&pool, &book.id).await;

        // Then: Should return the book
        assert!(result.is_ok());
        let found_book = result.unwrap();
        assert_eq!(found_book.id, book.id);
        assert_eq!(found_book.title, book.title);
    }

    #[tokio::test]
    async fn should_return_error_when_book_not_found() {
        // Given: An empty database
        let (pool, _temp_dir) = setup_test_db().await;

        // When: Finding a non-existent book
        let result = find_by_id(&pool, "non-existent-id").await;

        // Then: Should return BookNotFound error
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), EzBooksError::BookNotFound(_)));
    }

    #[tokio::test]
    async fn should_find_all_books() {
        // Given: Multiple books in the database
        let (pool, _temp_dir) = setup_test_db().await;
        let book1 = create_test_book();
        let book2 = Book::new("Second Book".to_string(), "/path/to/book2.epub".to_string());
        insert(&pool, &book1).await.unwrap();
        insert(&pool, &book2).await.unwrap();

        // When: Finding all books
        let result = find_all(&pool).await;

        // Then: Should return all books
        assert!(result.is_ok());
        let books = result.unwrap();
        assert_eq!(books.len(), 2);
    }

    #[tokio::test]
    async fn should_return_books_in_descending_order_by_created_at() {
        // Given: Multiple books inserted with different timestamps
        let (pool, _temp_dir) = setup_test_db().await;
        let book1 = create_test_book();
        std::thread::sleep(std::time::Duration::from_millis(10));
        let book2 = Book::new("Second Book".to_string(), "/path/to/book2.epub".to_string());

        insert(&pool, &book1).await.unwrap();
        insert(&pool, &book2).await.unwrap();

        // When: Finding all books
        let books = find_all(&pool).await.unwrap();

        // Then: Should return books in descending order (newest first)
        assert_eq!(books[0].id, book2.id);
        assert_eq!(books[1].id, book1.id);
    }

    #[tokio::test]
    async fn should_delete_book_successfully() {
        // Given: A book in the database
        let (pool, _temp_dir) = setup_test_db().await;
        let book = create_test_book();
        insert(&pool, &book).await.unwrap();

        // When: Deleting the book
        let result = delete(&pool, &book.id).await;

        // Then: Should succeed
        assert!(result.is_ok());

        // And: Book should no longer exist
        let find_result = find_by_id(&pool, &book.id).await;
        assert!(find_result.is_err());
    }

    #[tokio::test]
    async fn should_return_error_when_deleting_non_existent_book() {
        // Given: An empty database
        let (pool, _temp_dir) = setup_test_db().await;

        // When: Deleting a non-existent book
        let result = delete(&pool, "non-existent-id").await;

        // Then: Should return BookNotFound error
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), EzBooksError::BookNotFound(_)));
    }

    #[tokio::test]
    async fn should_insert_subject_successfully() {
        // Given: A book in the database
        let (pool, _temp_dir) = setup_test_db().await;
        let book = create_test_book();
        insert(&pool, &book).await.unwrap();

        // When: Inserting a subject
        let result = insert_subject(&pool, &book.id, "Fiction").await;

        // Then: Should succeed
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn should_find_subjects_by_book_id() {
        // Given: A book with multiple subjects
        let (pool, _temp_dir) = setup_test_db().await;
        let book = create_test_book();
        insert(&pool, &book).await.unwrap();
        insert_subject(&pool, &book.id, "Fiction").await.unwrap();
        insert_subject(&pool, &book.id, "Science Fiction")
            .await
            .unwrap();

        // When: Finding subjects for the book
        let result = find_subjects_by_book_id(&pool, &book.id).await;

        // Then: Should return all subjects
        assert!(result.is_ok());
        let subjects = result.unwrap();
        assert_eq!(subjects.len(), 2);
        assert!(subjects.contains(&"Fiction".to_string()));
        assert!(subjects.contains(&"Science Fiction".to_string()));
    }

    #[tokio::test]
    async fn should_delete_subjects_when_book_deleted() {
        // Given: A book with subjects
        let (pool, _temp_dir) = setup_test_db().await;
        let book = create_test_book();
        insert(&pool, &book).await.unwrap();
        insert_subject(&pool, &book.id, "Fiction").await.unwrap();

        // When: Deleting the book
        delete(&pool, &book.id).await.unwrap();

        // Then: Subjects should also be deleted (cascade)
        let subjects = find_subjects_by_book_id(&pool, &book.id).await.unwrap();
        assert_eq!(subjects.len(), 0);
    }

    #[tokio::test]
    async fn should_prevent_duplicate_subjects() {
        // Given: A book with a subject
        let (pool, _temp_dir) = setup_test_db().await;
        let book = create_test_book();
        insert(&pool, &book).await.unwrap();
        insert_subject(&pool, &book.id, "Fiction").await.unwrap();

        // When: Trying to insert the same subject again
        let result = insert_subject(&pool, &book.id, "Fiction").await;

        // Then: Should fail (unique constraint)
        assert!(result.is_err());
    }
}
