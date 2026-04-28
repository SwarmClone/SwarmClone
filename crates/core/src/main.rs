use utils::log;
use utils::config as cfg;

fn main() {
    log::set_log_level(log::LogLevel::Debug);

    log::info!("main", "配置文件: {:?}", cfg::path());

    match cfg::get("app.name", String::new()) {
        Ok(name) if !name.is_empty() => log::info!("main", "应用: {}", name),
        Ok(_) => log::info!("main", "应用: (未设置)"),
        Err(e) => log::error!("main", "读取失败: {}", e),
    }

    match cfg::get("server.port", 8080) {
        Ok(port) => log::info!("main", "端口: {}", port),
        Err(e) => log::error!("main", "读取失败: {}", e),
    }

    cfg::register_with_callback("server.port", |v: &toml::Value| {
        log::info!("回调", "端口变更: {}", v);
        if let Some(p) = v.as_integer() {
            if p < 1024 || p > 65535 {
                return Err("端口必须在 1024-65535".into());
            }
        }
        Ok(())
    });

    cfg::register("app.name");

    log::info!("main", "设置端口为 9090...");
    let _ = cfg::set("server.port", 9090);

    log::info!("main", "尝试无效端口...");
    let _ = cfg::set("server.port", 80);
}
