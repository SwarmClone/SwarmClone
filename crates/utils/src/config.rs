use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;
use std::sync::{Mutex, OnceLock};

use toml::Value;

// =============================================================================
// 配置值类型trait
// =============================================================================

/// 从toml::Value提取的类型
pub trait FromConfigValue: Sized {
    fn from_value(val: &Value) -> Option<Self>;
}

/// 可以存入配置的类型
pub trait IntoConfigValue {
    fn into_value(self) -> Value;
}

impl FromConfigValue for String {
    fn from_value(val: &Value) -> Option<Self> {
        val.as_str().map(String::from)
    }
}

impl FromConfigValue for i64 {
    fn from_value(val: &Value) -> Option<Self> {
        val.as_integer()
    }
}

impl FromConfigValue for f64 {
    fn from_value(val: &Value) -> Option<Self> {
        val.as_float()
    }
}

impl FromConfigValue for bool {
    fn from_value(val: &Value) -> Option<Self> {
        val.as_bool()
    }
}

impl IntoConfigValue for &str {
    fn into_value(self) -> Value {
        Value::String(self.to_string())
    }
}

impl IntoConfigValue for String {
    fn into_value(self) -> Value {
        Value::String(self)
    }
}

impl IntoConfigValue for i64 {
    fn into_value(self) -> Value {
        Value::Integer(self)
    }
}

impl IntoConfigValue for i32 {
    fn into_value(self) -> Value {
        Value::Integer(self as i64)
    }
}

impl IntoConfigValue for f64 {
    fn into_value(self) -> Value {
        Value::Float(self)
    }
}

impl IntoConfigValue for bool {
    fn into_value(self) -> Value {
        Value::Boolean(self)
    }
}

impl<V: IntoConfigValue> IntoConfigValue for HashMap<String, V> {
    fn into_value(self) -> Value {
        let map = self.into_iter()
            .map(|(k, v)| (k, v.into_value()))
            .collect();
        Value::Table(map)
    }
}

impl<V: IntoConfigValue> IntoConfigValue for Vec<V> {
    fn into_value(self) -> Value {
        Value::Array(self.into_iter().map(|v| v.into_value()).collect())
    }
}

/// 配置变更回调
type Callback = Box<dyn Fn(&Value) -> Result<(), String> + Send + Sync>;

pub struct Config {
    path: PathBuf,
    values: HashMap<String, Value>,
    callbacks: HashMap<String, Vec<Callback>>,
}

impl Config {
    fn new() -> Self {
        let path = exe_dir().join("config.toml");
        let mut cfg = Self {
            path,
            values: HashMap::new(),
            callbacks: HashMap::new(),
        };
        let _ = cfg.ensure_load();
        cfg
    }

    /// 确保配置已加载，不存在则创建
    fn ensure_load(&mut self) -> Result<(), String> {
        if !self.path.exists() {
            let parent = self.path.parent().ok_or("获取父目录失败")?;
            fs::create_dir_all(parent).map_err(|e| e.to_string())?;
            fs::write(&self.path, "").map_err(|e| e.to_string())?;
        }
        self.load()
    }

    /// 从文件加载
    fn load(&mut self) -> Result<(), String> {
        let content = fs::read_to_string(&self.path).map_err(|e| e.to_string())?;
        let val: Value = toml::from_str(&content).map_err(|e| e.to_string())?;
        if let Value::Table(table) = val {
            self.flatten(table, String::new());
        }
        Ok(())
    }

    fn flatten(&mut self, table: toml::map::Map<String, Value>, prefix: String) {
        for (k, v) in table {
            let key = if prefix.is_empty() { k } else { format!("{}.{}", prefix, k) };
            match v {
                Value::Table(t) => self.flatten(t, key),
                other => { self.values.insert(key, other); }
            }
        }
    }

    /// 设置值并触发回调
    fn set(&mut self, key: &str, val: Value) -> Result<(), String> {
        self.values.insert(key.into(), val.clone());
        if let Some(cbs) = self.callbacks.get(key) {
            for cb in cbs { cb(&val)?; }
        }
        Ok(())
    }

    /// 注册key并可选绑定回调
    fn register(&mut self, key: &str, cb: Option<Callback>) {
        if let Some(cb) = cb {
            self.callbacks.entry(key.into()).or_default().push(cb);
        }
    }
}

/// 获取可执行文件目录
fn exe_dir() -> PathBuf {
    std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|p| p.to_path_buf()))
        .unwrap_or_else(|| PathBuf::from("."))
}

// =============================================================================
// 全局单例
// =============================================================================

static INSTANCE: OnceLock<Mutex<Config>> = OnceLock::new();

fn instance() -> &'static Mutex<Config> {
    INSTANCE.get_or_init(|| Mutex::new(Config::new()))
}

pub fn get<T: FromConfigValue>(key: &str, default: T) -> Result<T, String> {
    let guard = instance().lock().map_err(|e| e.to_string())?;
    match guard.values.get(key) {
        Some(val) => T::from_value(val).ok_or_else(|| {
            format!("配置 '{}' 类型不匹配", key)
        }),
        None => Ok(default),
    }
}

pub fn set(key: &str, val: impl IntoConfigValue) -> Result<(), String> {
    instance().lock().map_err(|e| e.to_string())?.set(key, val.into_value())
}

/// 注册key，可选绑定回调
pub fn register(key: &str) {
    if let Ok(mut cfg) = instance().lock() {
        cfg.register(key, None);
    }
}

/// 注册key并绑定回调
pub fn register_with_callback<F>(key: &str, cb: F)
where
    F: Fn(&Value) -> Result<(), String> + Send + Sync + 'static,
{
    if let Ok(mut cfg) = instance().lock() {
        cfg.register(key, Some(Box::new(cb)));
    }
}

/// 获取配置文件路径
pub fn path() -> PathBuf {
    instance().lock().map(|c| c.path.clone()).unwrap_or_default()
}
