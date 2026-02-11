use crate::error::Result;
use std::env;

#[derive(Debug, Clone)]
pub struct Config {
    pub server_host: String,
    pub server_port: u16,
    pub database_url: String,
    pub storage_path: String,
    pub openlibrary_api_url: String,
}

impl Config {
    pub fn from_env() -> Result<Self> {
        Ok(Self {
            server_host: env::var("SERVER_HOST").unwrap_or_else(|_| "127.0.0.1".to_string()),
            server_port: env::var("SERVER_PORT")
                .ok()
                .and_then(|p| p.parse().ok())
                .unwrap_or(8080),
            database_url: env::var("DATABASE_URL")
                .unwrap_or_else(|_| "sqlite://data/ez-books.db".to_string()),
            storage_path: env::var("STORAGE_PATH").unwrap_or_else(|_| "./data".to_string()),
            openlibrary_api_url: env::var("OPENLIBRARY_API_URL")
                .unwrap_or_else(|_| "https://openlibrary.org".to_string()),
        })
    }

    pub fn server_address(&self) -> String {
        format!("{}:{}", self.server_host, self.server_port)
    }
}

impl Default for Config {
    fn default() -> Self {
        Self::from_env().expect("Failed to load configuration")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn should_create_config_with_defaults() {
        // Given/When: Creating config from environment (with no vars set)
        let config = Config::from_env().unwrap();

        // Then: Should use default values
        assert_eq!(config.server_host, "127.0.0.1");
        assert_eq!(config.server_port, 8080);
        assert_eq!(config.database_url, "sqlite://data/ez-books.db");
        assert_eq!(config.storage_path, "./data");
        assert_eq!(config.openlibrary_api_url, "https://openlibrary.org");
    }

    #[test]
    fn should_format_server_address() {
        // Given: A config
        let config = Config::from_env().unwrap();

        // When: Getting server address
        let address = config.server_address();

        // Then: Should be formatted correctly
        assert_eq!(address, "127.0.0.1:8080");
    }

    #[test]
    fn should_respect_custom_port() {
        // Given: Custom port in environment
        env::set_var("SERVER_PORT", "3000");

        // When: Creating config
        let config = Config::from_env().unwrap();

        // Then: Should use custom port
        assert_eq!(config.server_port, 3000);

        // Cleanup
        env::remove_var("SERVER_PORT");
    }
}
