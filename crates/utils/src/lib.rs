pub mod logger;

// 重新导出常用类型与函数到 crate 根，方便外部直接 `use utils::{info, LogLevel};`
pub use logger::{set_log_level, set_log_target, log, LogLevel};

// 别名模块，支持 `use utils::log;` 后通过 `log::info!` / `log::set_log_level` 调用
pub mod log {
    pub use crate::logger::{LogLevel, log, set_log_level, set_log_target};
    pub use crate::debug;
    pub use crate::info;
    pub use crate::warn;
    pub use crate::error;
}
