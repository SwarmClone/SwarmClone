use utils::log;

fn main() {
    // 设置全局日志级别
    log::set_log_level(log::LogLevel::Debug);

    log::debug!("main1", "This is a debug message.");
    log::info!("main1", "This is an info message.");
    log::warn!("main2", "This is a warning message.");
    log::error!("main2", "This is an error message.");
}
