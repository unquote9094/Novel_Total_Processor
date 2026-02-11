use crate::book_model::Book;
use crate::html_templates::{escape_html, html_footer, html_header};

pub fn render_gallery(books: Vec<Book>) -> String {
    let mut html = html_header("EZ-Books Library", "gallery.css");

    html.push_str(&render_header());
    html.push_str(&render_main(books));
    html.push_str(&html_footer(Some("upload.js")));

    html
}

fn render_header() -> String {
    r#"<header>
    <h1>EZ-Books Library</h1>
    <div id="upload-section">
        <form id="upload-form" enctype="multipart/form-data">
            <input type="file" name="file" accept=".epub" required>
            <button type="submit">Upload EPUB</button>
        </form>
        <div id="upload-status"></div>
    </div>
</header>"#
        .to_string()
}

fn render_main(books: Vec<Book>) -> String {
    let mut html = String::from(r#"<main><div id="gallery">"#);

    if books.is_empty() {
        html.push_str(&render_empty_state());
    } else {
        for book in books {
            html.push_str(&render_book_card(&book));
        }
    }

    html.push_str("</div></main>");
    html
}

fn render_empty_state() -> String {
    r#"<div class="empty-state">
    <h2>No books yet</h2>
    <p>Upload your first EPUB to get started!</p>
</div>"#
        .to_string()
}

fn render_book_card(book: &Book) -> String {
    let title = escape_html(&book.title);
    let author = book
        .author
        .as_ref()
        .map(|a| escape_html(a))
        .unwrap_or_else(|| "Unknown Author".to_string());
    let cover_url = format!("/covers/{}", escape_html(&book.id));
    let reader_url = format!("/reader/{}", escape_html(&book.id));

    format!(
        r#"<div class="book-card" data-book-id="{}">
    <img src="{}" alt="{}" onerror="this.style.backgroundColor='#bdc3c7'">
    <h3>{}</h3>
    <p class="author">{}</p>
    <div class="actions">
        <a href="{}">Read</a>
        <button class="delete" data-id="{}">Delete</button>
    </div>
</div>"#,
        escape_html(&book.id),
        cover_url,
        title,
        title,
        author,
        reader_url,
        escape_html(&book.id)
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_book() -> Book {
        let mut book = Book::new("Test Book".to_string(), "/path/to/book.epub".to_string());
        book.author = Some("Test Author".to_string());
        book
    }

    #[test]
    fn should_render_complete_gallery_page() {
        // Given: A list of books
        let books = vec![create_test_book()];

        // When: Rendering gallery
        let html = render_gallery(books);

        // Then: Should contain all necessary elements
        assert!(html.contains("<!DOCTYPE html>"));
        assert!(html.contains("<title>EZ-Books Library</title>"));
        assert!(html.contains("gallery.css"));
        assert!(html.contains("upload.js"));
        assert!(html.contains("<header>"));
        assert!(html.contains("<main>"));
        assert!(html.contains("</html>"));
    }

    #[test]
    fn should_render_upload_form_in_header() {
        // Given: An empty book list
        let books = vec![];

        // When: Rendering gallery
        let html = render_gallery(books);

        // Then: Should include upload form
        assert!(html.contains(r#"<form id="upload-form""#));
        assert!(html.contains(r#"<input type="file""#));
        assert!(html.contains(r#"accept=".epub""#));
        assert!(html.contains(r#"<button type="submit">Upload EPUB</button>"#));
    }

    #[test]
    fn should_render_empty_state_when_no_books() {
        // Given: Empty book list
        let books = vec![];

        // When: Rendering gallery
        let html = render_gallery(books);

        // Then: Should show empty state
        assert!(html.contains("No books yet"));
        assert!(html.contains("Upload your first EPUB to get started!"));
    }

    #[test]
    fn should_render_book_cards() {
        // Given: A book
        let book = create_test_book();
        let book_id = book.id.clone();
        let books = vec![book];

        // When: Rendering gallery
        let html = render_gallery(books);

        // Then: Should render book card with all elements
        assert!(html.contains("Test Book"));
        assert!(html.contains("Test Author"));
        assert!(html.contains(&format!("/covers/{}", book_id)));
        assert!(html.contains(&format!("/reader/{}", book_id)));
        assert!(html.contains(r#"class="delete""#));
    }

    #[test]
    fn should_escape_html_in_book_data() {
        // Given: A book with HTML characters in title
        let mut book = Book::new(
            "<script>alert('XSS')</script>".to_string(),
            "/path".to_string(),
        );
        book.author = Some("Author & Co.".to_string());
        let books = vec![book];

        // When: Rendering gallery
        let html = render_gallery(books);

        // Then: Should escape HTML entities
        assert!(html.contains("&lt;script&gt;"));
        assert!(html.contains("&amp;"));
        assert!(!html.contains("<script>alert"));
    }

    #[test]
    fn should_handle_book_without_author() {
        // Given: A book without author
        let book = Book::new("Test Book".to_string(), "/path".to_string());
        let books = vec![book];

        // When: Rendering gallery
        let html = render_gallery(books);

        // Then: Should show "Unknown Author"
        assert!(html.contains("Unknown Author"));
    }

    #[test]
    fn should_render_multiple_books() {
        // Given: Multiple books
        let book1 = create_test_book();
        let mut book2 = Book::new("Second Book".to_string(), "/path2".to_string());
        book2.author = Some("Second Author".to_string());
        let books = vec![book1, book2];

        // When: Rendering gallery
        let html = render_gallery(books);

        // Then: Should render all books
        assert!(html.contains("Test Book"));
        assert!(html.contains("Second Book"));
        assert!(html.contains("Test Author"));
        assert!(html.contains("Second Author"));
    }
}
