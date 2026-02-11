use crate::error::{EzBooksError, Result};
use epub::doc::EpubDoc;
use image::imageops::FilterType;
use image::{GenericImageView, ImageFormat};
use std::io::Cursor;
use std::path::Path;
use tracing::{info, instrument, warn};

const COVER_WIDTH: u32 = 300;
const COVER_HEIGHT: u32 = 450;

#[instrument(skip_all, fields(path = %path.as_ref().display()))]
pub fn extract_cover(path: impl AsRef<Path>) -> Result<Option<Vec<u8>>> {
    let path = path.as_ref();
    info!(path = %path.display(), "Extracting cover from EPUB");

    let mut doc = EpubDoc::new(path).map_err(|e| {
        warn!(path = %path.display(), error = %e, "Failed to open EPUB for cover extraction");
        EzBooksError::EpubParse(format!("Failed to open EPUB: {}", e))
    })?;

    // Try to get cover from EPUB
    let cover_data = match doc.get_cover() {
        Some((data, _mime_type)) => {
            info!(size = data.len(), "Cover image found in EPUB");
            Some(data)
        }
        None => {
            warn!("No cover found in EPUB");
            None
        }
    };

    if let Some(data) = cover_data {
        // Process the cover image
        match process_cover_image(&data) {
            Ok(processed) => {
                info!(
                    original_size = data.len(),
                    processed_size = processed.len(),
                    "Cover processed successfully"
                );
                Ok(Some(processed))
            }
            Err(e) => {
                warn!(error = %e, "Failed to process cover image, using original");
                // If processing fails, return the original data
                Ok(Some(data))
            }
        }
    } else {
        info!("No cover image available");
        Ok(None)
    }
}

fn process_cover_image(data: &[u8]) -> Result<Vec<u8>> {
    // Load the image
    let img = image::load_from_memory(data)
        .map_err(|e| EzBooksError::ImageProcessing(format!("Failed to load image: {}", e)))?;

    // Calculate aspect ratio preserving dimensions
    let (width, height) = img.dimensions();
    let aspect_ratio = width as f32 / height as f32;
    let target_aspect_ratio = COVER_WIDTH as f32 / COVER_HEIGHT as f32;

    let (new_width, new_height) = if aspect_ratio > target_aspect_ratio {
        // Image is wider than target, constrain by width
        (COVER_WIDTH, (COVER_WIDTH as f32 / aspect_ratio) as u32)
    } else {
        // Image is taller than target, constrain by height
        ((COVER_HEIGHT as f32 * aspect_ratio) as u32, COVER_HEIGHT)
    };

    // Resize the image
    let resized = img.resize(new_width, new_height, FilterType::Lanczos3);

    // Convert to JPEG
    let mut output = Vec::new();
    let mut cursor = Cursor::new(&mut output);

    resized
        .write_to(&mut cursor, ImageFormat::Jpeg)
        .map_err(|e| EzBooksError::ImageProcessing(format!("Failed to encode JPEG: {}", e)))?;

    Ok(output)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn should_calculate_resize_dimensions_for_wide_image() {
        // Given: A wide image (landscape)
        let width = 800u32;
        let height = 400u32;
        let aspect_ratio = width as f32 / height as f32;
        let target_aspect_ratio = COVER_WIDTH as f32 / COVER_HEIGHT as f32;

        // When: Calculating new dimensions
        let (new_width, new_height) = if aspect_ratio > target_aspect_ratio {
            (COVER_WIDTH, (COVER_WIDTH as f32 / aspect_ratio) as u32)
        } else {
            ((COVER_HEIGHT as f32 * aspect_ratio) as u32, COVER_HEIGHT)
        };

        // Then: Should constrain by width
        assert_eq!(new_width, COVER_WIDTH);
        assert!(new_height <= COVER_HEIGHT);
    }

    #[test]
    fn should_calculate_resize_dimensions_for_tall_image() {
        // Given: A tall image (portrait)
        let width = 400u32;
        let height = 800u32;
        let aspect_ratio = width as f32 / height as f32;
        let target_aspect_ratio = COVER_WIDTH as f32 / COVER_HEIGHT as f32;

        // When: Calculating new dimensions
        let (new_width, new_height) = if aspect_ratio > target_aspect_ratio {
            (COVER_WIDTH, (COVER_WIDTH as f32 / aspect_ratio) as u32)
        } else {
            ((COVER_HEIGHT as f32 * aspect_ratio) as u32, COVER_HEIGHT)
        };

        // Then: Should constrain by height
        assert_eq!(new_height, COVER_HEIGHT);
        assert!(new_width <= COVER_WIDTH);
    }

    #[test]
    fn should_process_valid_image() {
        // Given: A simple 1x1 red PNG image
        let mut png_data = Vec::new();
        let img = image::RgbaImage::from_pixel(1, 1, image::Rgba([255, 0, 0, 255]));
        img.write_to(&mut Cursor::new(&mut png_data), ImageFormat::Png)
            .unwrap();

        // When: Processing the image
        let result = process_cover_image(&png_data);

        // Then: Should succeed and return JPEG data
        assert!(result.is_ok());
        let jpeg_data = result.unwrap();
        assert!(!jpeg_data.is_empty());
    }

    #[test]
    fn should_return_error_for_invalid_image_data() {
        // Given: Invalid image data
        let invalid_data = b"Not an image";

        // When: Processing the invalid data
        let result = process_cover_image(invalid_data);

        // Then: Should return error
        assert!(result.is_err());
        assert!(matches!(
            result.unwrap_err(),
            EzBooksError::ImageProcessing(_)
        ));
    }

    #[test]
    fn should_maintain_aspect_ratio() {
        // Given: A square image
        let size = 500u32;
        let img = image::RgbaImage::from_pixel(size, size, image::Rgba([100, 100, 100, 255]));
        let mut png_data = Vec::new();
        img.write_to(&mut Cursor::new(&mut png_data), ImageFormat::Png)
            .unwrap();

        // When: Processing the image
        let result = process_cover_image(&png_data);

        // Then: Should succeed
        assert!(result.is_ok());
        let jpeg_data = result.unwrap();

        // And: Should be able to load the processed image
        let processed_img = image::load_from_memory(&jpeg_data).unwrap();
        let (w, h) = processed_img.dimensions();

        // Should maintain square aspect ratio
        assert_eq!(w, h);
        assert!(w <= COVER_WIDTH);
        assert!(h <= COVER_HEIGHT);
    }

    // Note: Full integration tests with actual EPUB files will be added
    // in the tests directory once we have test fixtures
}
