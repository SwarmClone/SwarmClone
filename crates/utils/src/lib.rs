pub mod logger;

pub use logger::{LogLevel, set_log_level, set_log_target};

pub mod log {
    pub use crate::debug;
    pub use crate::error;
    pub use crate::info;
    pub use crate::logger::{LogLevel, set_log_level, set_log_target};
    pub use crate::warn;
}

pub mod config;
