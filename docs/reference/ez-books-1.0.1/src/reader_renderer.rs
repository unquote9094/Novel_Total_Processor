use crate::book_model::Book;
use crate::error::{EzBooksError, Result};
use crate::html_templates::{escape_html, html_footer, html_header};
use epub::doc::EpubDoc;
use std::path::Path;
use tracing::{info, instrument, warn};

pub fn render_reader(book: &Book, epub_content: String) -> String {
    let mut html = html_header(&book.title, "reader.css");

    html.push_str(&render_nav(&book.title));
    html.push_str(&render_content(&epub_content));
    html.push_str(&html_footer(None));

    html
}

fn render_nav(title: &str) -> String {
    format!(
        r#"<nav>
    <a href="/">&larr; Back to Library</a>
    <h2>{}</h2>
</nav>"#,
        escape_html(title)
    )
}

fn render_content(content: &str) -> String {
    format!(
        r#"<main>
    <article>
{}
    </article>
</main>"#,
        content
    )
}

#[instrument(skip_all, fields(path = %epub_path.as_ref().display()))]
pub fn extract_and_sanitize_content(epub_path: impl AsRef<Path>) -> Result<String> {
    let path = epub_path.as_ref();
    info!(path = %path.display(), "Extracting content from EPUB");

    let mut doc = EpubDoc::new(path).map_err(|e| {
        warn!(path = %path.display(), error = %e, "Failed to open EPUB for reading");
        EzBooksError::EpubParse(format!("Failed to open EPUB: {}", e))
    })?;

    let mut all_content = String::new();
    let spine_len = doc.spine.len();

    info!(chapters = spine_len, "Extracting chapters");

    // Iterate through all chapters in the spine (reading order)
    for i in 0..spine_len {
        doc.set_current_chapter(i);

        match doc.get_current_str() {
            Some((content, _mime)) => {
                let sanitized = sanitize_html(&content);
                all_content.push_str(&sanitized);
                all_content.push_str("\n<hr>\n");
            }
            None => {
                warn!(chapter = i, "Failed to read chapter");
            }
        }
    }

    info!(size = all_content.len(), "Content extraction completed");
    Ok(all_content)
}

fn sanitize_html(html: &str) -> String {
    // Use ammonia to sanitize HTML
    ammonia::clean(html)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_book() -> Book {
        Book::new("Test Book".to_string(), "/path/to/book.epub".to_string())
    }

    #[test]
    fn should_render_complete_reader_page() {
        // Given: A book and content
        let book = create_test_book();
        let content = "<p>Test content</p>".to_string();

        // When: Rendering reader
        let html = render_reader(&book, content);

        // Then: Should contain all necessary elements
        assert!(html.contains("<!DOCTYPE html>"));
        assert!(html.contains("<title>Test Book</title>"));
        assert!(html.contains("reader.css"));
        assert!(html.contains("<nav>"));
        assert!(html.contains("<article>"));
        assert!(html.contains("Test content"));
        assert!(html.contains("</html>"));
    }

    #[test]
    fn should_render_back_link() {
        // Given: A book
        let book = create_test_book();
        let content = String::new();

        // When: Rendering reader
        let html = render_reader(&book, content);

        // Then: Should include back link
        assert!(html.contains(r#"<a href="/">&larr; Back to Library</a>"#));
    }

    #[test]
    fn should_display_book_title_in_nav() {
        // Given: A book with specific title
        let book = create_test_book();
        let content = String::new();

        // When: Rendering reader
        let html = render_reader(&book, content);

        // Then: Should show title in navigation
        assert!(html.contains("<h2>Test Book</h2>"));
    }

    #[test]
    fn should_escape_html_in_title() {
        // Given: A book with HTML characters in title
        let book = Book::new(
            "<script>alert('XSS')</script>".to_string(),
            "/path".to_string(),
        );
        let content = String::new();

        // When: Rendering reader
        let html = render_reader(&book, content);

        // Then: Should escape HTML in title
        assert!(html.contains("&lt;script&gt;"));
        assert!(!html.contains("<script>alert"));
    }

    #[test]
    fn should_wrap_content_in_article() {
        // Given: Some content
        let book = create_test_book();
        let content = "<p>Chapter 1</p><p>Chapter 2</p>".to_string();

        // When: Rendering reader
        let html = render_reader(&book, content);

        // Then: Should wrap in article tags
        assert!(html.contains("<article>"));
        assert!(html.contains("</article>"));
        assert!(html.contains("Chapter 1"));
        assert!(html.contains("Chapter 2"));
    }

    #[test]
    fn should_not_include_javascript() {
        // Given: A book
        let book = create_test_book();
        let content = String::new();

        // When: Rendering reader
        let html = render_reader(&book, content);

        // Then: Should not include any script tags
        assert!(!html.contains("<script"));
    }

    #[test]
    fn should_sanitize_dangerous_html() {
        // Given: HTML with script tags
        let html = r#"<p>Safe content</p><script>alert('XSS')</script><p>More content</p>"#;

        // When: Sanitizing
        let sanitized = sanitize_html(html);

        // Then: Should remove script tags
        assert!(!sanitized.contains("<script"));
        assert!(sanitized.contains("Safe content"));
        assert!(sanitized.contains("More content"));
    }

    #[test]
    fn should_preserve_safe_html_tags() {
        // Given: HTML with safe formatting tags
        let html = r#"<p>This is <strong>bold</strong> and <em>italic</em> text</p>"#;

        // When: Sanitizing
        let sanitized = sanitize_html(html);

        // Then: Should preserve safe tags
        assert!(sanitized.contains("<strong>"));
        assert!(sanitized.contains("<em>"));
        assert!(sanitized.contains("<p>"));
    }

    #[test]
    fn should_sanitize_onclick_attributes() {
        // Given: HTML with onclick attribute
        let html = "<a href=\"#\" onclick=\"alert('XSS')\">Click me</a>";

        // When: Sanitizing
        let sanitized = sanitize_html(html);

        // Then: Should remove onclick attribute
        assert!(!sanitized.contains("onclick"));
        assert!(sanitized.contains("Click me"));
    }
}
