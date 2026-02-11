/// Reusable HTML template functions
pub fn html_header(title: &str, css_file: &str) -> String {
    format!(
        r#"<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{}</title>
    <link rel="stylesheet" href="/static/css/{}">
</head>
<body>"#,
        escape_html(title),
        css_file
    )
}

pub fn html_footer(include_js: Option<&str>) -> String {
    let js_tag = if let Some(js_file) = include_js {
        format!(r#"<script src="/static/js/{}"></script>"#, js_file)
    } else {
        String::new()
    };

    format!(
        r#"{}
</body>
</html>"#,
        js_tag
    )
}

pub fn escape_html(text: &str) -> String {
    text.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&#x27;")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn should_generate_html_header() {
        // Given: Title and CSS file
        let title = "Test Page";
        let css = "test.css";

        // When: Generating header
        let header = html_header(title, css);

        // Then: Should contain proper HTML structure
        assert!(header.contains("<!DOCTYPE html>"));
        assert!(header.contains("<html lang=\"en\">"));
        assert!(header.contains("<title>Test Page</title>"));
        assert!(header.contains(r#"<link rel="stylesheet" href="/static/css/test.css">"#));
        assert!(header.contains("<body>"));
    }

    #[test]
    fn should_generate_html_footer_with_js() {
        // Given: A JavaScript file
        let js_file = "script.js";

        // When: Generating footer with JS
        let footer = html_footer(Some(js_file));

        // Then: Should include script tag
        assert!(footer.contains(r#"<script src="/static/js/script.js"></script>"#));
        assert!(footer.contains("</body>"));
        assert!(footer.contains("</html>"));
    }

    #[test]
    fn should_generate_html_footer_without_js() {
        // Given/When: Generating footer without JS
        let footer = html_footer(None);

        // Then: Should not include script tag
        assert!(!footer.contains("<script"));
        assert!(footer.contains("</body>"));
        assert!(footer.contains("</html>"));
    }

    #[test]
    fn should_escape_html_entities() {
        // Given: Text with special characters
        let text = r#"<script>alert("XSS & stuff")</script>"#;

        // When: Escaping HTML
        let escaped = escape_html(text);

        // Then: Should escape all special characters
        assert_eq!(
            escaped,
            "&lt;script&gt;alert(&quot;XSS &amp; stuff&quot;)&lt;/script&gt;"
        );
    }

    #[test]
    fn should_escape_single_quotes() {
        // Given: Text with single quotes
        let text = "It's a test";

        // When: Escaping HTML
        let escaped = escape_html(text);

        // Then: Should escape single quotes
        assert_eq!(escaped, "It&#x27;s a test");
    }

    #[test]
    fn should_handle_empty_string() {
        // Given: Empty string
        let text = "";

        // When: Escaping HTML
        let escaped = escape_html(text);

        // Then: Should return empty string
        assert_eq!(escaped, "");
    }

    #[test]
    fn should_handle_text_without_special_chars() {
        // Given: Plain text
        let text = "Hello World";

        // When: Escaping HTML
        let escaped = escape_html(text);

        // Then: Should return unchanged
        assert_eq!(escaped, "Hello World");
    }
}
