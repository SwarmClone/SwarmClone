use std::io::Write;
use std::sync::{Mutex, OnceLock};

use chrono::Local;
use colored::Colorize;

/// 日志级别，按严重程度从低到高排列。
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum LogLevel {
    Debug,
    Info,
    Warn,
    Error,
}

impl LogLevel {
    /// 返回该级别对应的颜色字符串（用于终端输出）。
    fn colored_str(&self) -> String {
        match self {
            LogLevel::Debug => "DEBUG".bright_blue().to_string(),
            LogLevel::Info => "INFO".bright_green().to_string(),
            LogLevel::Warn => "WARN".bright_yellow().to_string(),
            LogLevel::Error => "ERROR".bright_red().to_string(),
        }
    }

    /// 返回该级别对应的消息颜色。
    fn colorize_msg(&self, msg: &str) -> String {
        match self {
            LogLevel::Debug => msg.bright_blue().to_string(),
            LogLevel::Info => msg.bright_green().to_string(),
            LogLevel::Warn => msg.bright_yellow().to_string(),
            LogLevel::Error => msg.bright_red().to_string(),
        }
    }
}

impl std::fmt::Display for LogLevel {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            LogLevel::Debug => write!(f, "DEBUG"),
            LogLevel::Info => write!(f, "INFO"),
            LogLevel::Warn => write!(f, "WARN"),
            LogLevel::Error => write!(f, "ERROR"),
        }
    }
}

pub struct Logger {
    min_level: LogLevel,
    target: Box<dyn Write + Send + 'static>,
}

impl Logger {
    /// 创建默认日志器，最小级别为 `Info`，输出到 `stdout`。
    pub fn new() -> Self {
        Self {
            min_level: LogLevel::Info,
            target: Box::new(std::io::stdout()),
        }
    }

    /// 设置最小输出级别。低于此级别的日志将被丢弃。
    pub fn set_level(&mut self, level: LogLevel) {
        self.min_level = level;
    }

    /// 设置自定义输出目标（如文件）。默认是 `stdout`。
    pub fn set_target<W: Write + Send + 'static>(&mut self, target: W) {
        self.target = Box::new(target);
    }

    /// 核心日志输出方法。
    ///
    /// 格式：`yyyy-MM-dd HH:mm:ss.SSS LEVEL --- [name] : msg`
    pub fn log(&mut self, level: LogLevel, func: &str, msg: &str) {
        if level < self.min_level {
            return;
        }

        let now = Local::now();
        let time_str = format!(
            "{}.{:03}",
            now.format("%Y-%m-%d %H:%M:%S"),
            now.timestamp_subsec_millis()
        );

        let colored_level = level.colored_str();
        let colored_msg = level.colorize_msg(msg);

        let line = format!(
            "{} {:<14} --- [{}] : {}\n",
            time_str, colored_level, func, colored_msg
        );

        // 忽略写入失败，避免日志系统本身 panic
        let _ = self.target.write_all(line.as_bytes());
        let _ = self.target.flush();
    }
}

impl Default for Logger {
    fn default() -> Self {
        Self::new()
    }
}

// =============================================================================
// 全局单例
// =============================================================================

static LOGGER: OnceLock<Mutex<Logger>> = OnceLock::new();

fn global_logger() -> &'static Mutex<Logger> {
    LOGGER.get_or_init(|| Mutex::new(Logger::new()))
}

/// 设置全局日志器的最小输出级别。
pub fn set_log_level(level: LogLevel) {
    if let Ok(mut logger) = global_logger().lock() {
        logger.set_level(level);
    }
}

/// 设置全局日志器的输出目标。
pub fn set_log_target<W: Write + Send + 'static>(target: W) {
    if let Ok(mut logger) = global_logger().lock() {
        logger.set_target(target);
    }
}

/// 手动调用日志输出（通常直接使用宏更方便）。
pub fn log(level: LogLevel, func: &str, msg: &str) {
    if let Ok(mut logger) = global_logger().lock() {
        logger.log(level, func, msg);
    }
}

// =============================================================================
// 便捷宏
// =============================================================================

/// 底层日志宏，需手动传入级别与函数名。
/// module 使用完整的 `module_path!()`（如 `my_app::main`）。
#[macro_export]
macro_rules! log {
    ($level:expr, $func:expr, $($arg:tt)*) => {
        $crate::logger::log(
            $level,
            $func,
            &format!($($arg)*)
        )
    };
}

/// 输出 `Debug` 级别日志。
#[macro_export]
macro_rules! debug {
    ($func:expr, $($arg:tt)*) => {
        $crate::log!($crate::logger::LogLevel::Debug, $func, $($arg)*)
    };
}

/// 输出 `Info` 级别日志。
#[macro_export]
macro_rules! info {
    ($func:expr, $($arg:tt)*) => {
        $crate::log!($crate::logger::LogLevel::Info, $func, $($arg)*)
    };
}

/// 输出 `Warn` 级别日志。
#[macro_export]
macro_rules! warn {
    ($func:expr, $($arg:tt)*) => {
        $crate::log!($crate::logger::LogLevel::Warn, $func, $($arg)*)
    };
}

/// 输出 `Error` 级别日志。
#[macro_export]
macro_rules! error {
    ($func:expr, $($arg:tt)*) => {
        $crate::log!($crate::logger::LogLevel::Error, $func, $($arg)*)
    };
}
