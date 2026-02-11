use crate::error::Result;
use sqlx::sqlite::{SqliteConnectOptions, SqlitePool, SqlitePoolOptions};
use std::str::FromStr;
use tracing::{info, instrument};

pub type DatabasePool = SqlitePool;

#[instrument]
pub async fn create_pool(database_url: &str) -> Result<DatabasePool> {
    info!("Creating database connection pool");

    let options = SqliteConnectOptions::from_str(database_url)?
        .create_if_missing(true)
        .foreign_keys(true);

    let pool = SqlitePoolOptions::new()
        .max_connections(5)
        .connect_with(options)
        .await?;

    info!("Database connection pool created successfully");
    Ok(pool)
}

#[instrument(skip(pool))]
pub async fn run_migrations(pool: &DatabasePool) -> Result<()> {
    info!("Running database migrations");

    // Read and execute migration file
    let migration_sql = include_str!("../migrations/001_initial_schema.sql");

    sqlx::query(migration_sql).execute(pool).await?;

    info!("Database migrations completed successfully");
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    async fn create_test_pool() -> (DatabasePool, TempDir) {
        let temp_dir = TempDir::new().expect("Failed to create temp dir");
        let db_path = temp_dir.path().join("test.db");
        let database_url = format!("sqlite://{}", db_path.display());

        let pool = create_pool(&database_url)
            .await
            .expect("Failed to create pool");

        (pool, temp_dir)
    }

    #[tokio::test]
    async fn should_create_database_pool() {
        // Given: A temporary database URL
        let temp_dir = TempDir::new().unwrap();
        let db_path = temp_dir.path().join("test.db");
        let database_url = format!("sqlite://{}", db_path.display());

        // When: Creating a connection pool
        let result = create_pool(&database_url).await;

        // Then: Pool should be created successfully
        assert!(result.is_ok());
        let pool = result.unwrap();
        assert!(!pool.is_closed());
    }

    #[tokio::test]
    async fn should_create_database_file_if_missing() {
        // Given: A non-existent database path
        let temp_dir = TempDir::new().unwrap();
        let db_path = temp_dir.path().join("new_db.db");
        let database_url = format!("sqlite://{}", db_path.display());

        // When: Creating a pool
        let _ = create_pool(&database_url).await.unwrap();

        // Then: Database file should be created
        assert!(db_path.exists());
    }

    #[tokio::test]
    async fn should_run_migrations_successfully() {
        // Given: A fresh database pool
        let (pool, _temp_dir) = create_test_pool().await;

        // When: Running migrations
        let result = run_migrations(&pool).await;

        // Then: Migrations should complete without error
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn should_create_books_table_after_migration() {
        // Given: A database with migrations run
        let (pool, _temp_dir) = create_test_pool().await;
        run_migrations(&pool).await.unwrap();

        // When: Querying the books table
        let result = sqlx::query("SELECT COUNT(*) as count FROM books")
            .fetch_one(&pool)
            .await;

        // Then: Query should succeed (table exists)
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn should_create_book_subjects_table_after_migration() {
        // Given: A database with migrations run
        let (pool, _temp_dir) = create_test_pool().await;
        run_migrations(&pool).await.unwrap();

        // When: Querying the book_subjects table
        let result = sqlx::query("SELECT COUNT(*) as count FROM book_subjects")
            .fetch_one(&pool)
            .await;

        // Then: Query should succeed (table exists)
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn should_enforce_foreign_keys() {
        // Given: A database with migrations run
        let (pool, _temp_dir) = create_test_pool().await;
        run_migrations(&pool).await.unwrap();

        // When: Trying to insert a book_subject with non-existent book_id
        let result = sqlx::query(
            "INSERT INTO book_subjects (book_id, subject) VALUES ('non-existent', 'Fiction')",
        )
        .execute(&pool)
        .await;

        // Then: Should fail due to foreign key constraint
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn should_handle_multiple_migration_runs() {
        // Given: A database with migrations run once
        let (pool, _temp_dir) = create_test_pool().await;
        run_migrations(&pool).await.unwrap();

        // When: Running migrations again
        let result = run_migrations(&pool).await;

        // Then: Should succeed (using IF NOT EXISTS)
        assert!(result.is_ok());
    }
}
