use rust_embed::RustEmbed;
use warp::http::Response;
use warp::hyper::Body;
use warp::{reject, Filter, Rejection, Reply};

#[derive(RustEmbed)]
#[folder = "static/"]
pub struct StaticAssets;

pub fn serve_static() -> impl Filter<Extract = impl Reply, Error = Rejection> + Clone {
    warp::path("static")
        .and(warp::path::tail())
        .and_then(serve_embedded_file)
}

async fn serve_embedded_file(path: warp::path::Tail) -> Result<impl Reply, Rejection> {
    let path_str = path.as_str();

    let asset = StaticAssets::get(path_str).ok_or_else(reject::not_found)?;

    let mime = mime_guess::from_path(path_str).first_or_octet_stream();

    let response = Response::builder()
        .header("content-type", mime.as_ref())
        .header("cache-control", "public, max-age=3600")
        .body(Body::from(asset.data.into_owned()))
        .map_err(|_| reject::reject())?;

    Ok(response)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn should_embed_css_files() {
        // Given: The static assets are embedded
        // When: Accessing CSS files
        let gallery_css = StaticAssets::get("css/gallery.css");
        let reader_css = StaticAssets::get("css/reader.css");

        // Then: Files should be embedded
        assert!(gallery_css.is_some());
        assert!(reader_css.is_some());
    }

    #[test]
    fn should_embed_javascript_files() {
        // Given: The static assets are embedded
        // When: Accessing JavaScript files
        let upload_js = StaticAssets::get("js/upload.js");

        // Then: File should be embedded
        assert!(upload_js.is_some());
    }

    #[test]
    fn should_return_none_for_non_existent_files() {
        // Given: The static assets are embedded
        // When: Accessing a non-existent file
        let result = StaticAssets::get("non-existent.txt");

        // Then: Should return None
        assert!(result.is_none());
    }

    #[test]
    fn should_detect_correct_mime_types() {
        // Given: Various file paths
        let css_path = "styles.css";
        let js_path = "script.js";
        let jpg_path = "image.jpg";
        let html_path = "page.html";

        // When: Guessing MIME types
        let css_mime = mime_guess::from_path(css_path).first_or_octet_stream();
        let js_mime = mime_guess::from_path(js_path).first_or_octet_stream();
        let jpg_mime = mime_guess::from_path(jpg_path).first_or_octet_stream();
        let html_mime = mime_guess::from_path(html_path).first_or_octet_stream();

        // Then: MIME types should be correct
        assert_eq!(css_mime.as_ref(), "text/css");
        assert_eq!(js_mime.as_ref(), "text/javascript");
        assert_eq!(jpg_mime.as_ref(), "image/jpeg");
        assert_eq!(html_mime.as_ref(), "text/html");
    }

    #[test]
    fn should_handle_nested_paths() {
        // Given: Nested file paths
        // When: Accessing files in subdirectories
        let nested_css = StaticAssets::get("css/gallery.css");
        let nested_js = StaticAssets::get("js/upload.js");

        // Then: Should find files in subdirectories
        assert!(nested_css.is_some());
        assert!(nested_js.is_some());
    }
}
