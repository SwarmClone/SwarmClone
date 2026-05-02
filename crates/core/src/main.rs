use utils::log;

#[tokio::main]
async fn main() {
    log::set_log_level(log::LogLevel::Debug);
}