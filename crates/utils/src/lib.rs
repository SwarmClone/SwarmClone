pub mod logger;

pub use logger::{set_log_level, set_log_target, LogLevel};

pub mod log {
    pub use crate::logger::{LogLevel, set_log_level, set_log_target};
    pub use crate::debug;
    pub use crate::info;
    pub use crate::warn;
    pub use crate::error;
}

pub mod config;
