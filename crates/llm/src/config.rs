use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;
use std::sync::OnceLock;

use serde::Deserialize;

use crate::error::{LLMError, Result};

#[derive(Debug, Clone, Deserialize)]
pub struct ProviderConfig {
    #[serde(default)]
    pub kind: Option<String>,
    pub base_url: String,
    pub api_key: String,
    #[serde(default)]
    pub headers: Option<HashMap<String, String>>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct RoleConfig {
    pub provider: String,
    pub model: String,
    #[serde(default)]
    pub system_prompt: Option<String>,
    #[serde(default)]
    pub max_tokens: Option<u32>,
    #[serde(default)]
    pub temperature: Option<f64>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct LLMConfig {
    #[serde(default)]
    pub providers: HashMap<String, ProviderConfig>,
    #[serde(default)]
    pub roles: HashMap<String, RoleConfig>,
}

fn config_path() -> PathBuf {
    std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|p| p.to_path_buf()))
        .unwrap_or_else(|| PathBuf::from("."))
        .join("config.toml")
}

fn load_config() -> Result<LLMConfig> {
    let path = config_path();
    if !path.exists() {
        return Ok(LLMConfig {
            providers: HashMap::new(),
            roles: HashMap::new(),
        });
    }

    let content = fs::read_to_string(&path).map_err(|e| LLMError::Config(e.to_string()))?;
    let root: toml::Value =
        toml::from_str(&content).map_err(|e| LLMError::Config(e.to_string()))?;

    let llm_table = root
        .get("llm")
        .cloned()
        .unwrap_or(toml::Value::Table(toml::map::Map::new()));

    let config: LLMConfig = llm_table
        .try_into()
        .map_err(|e| LLMError::Config(format!("解析 llm 配置失败: {}", e)))?;

    Ok(config)
}

static CONFIG: OnceLock<LLMConfig> = OnceLock::new();

pub fn get_config() -> &'static LLMConfig {
    CONFIG.get_or_init(|| {
        load_config().unwrap_or_else(|e| {
            eprintln!("警告: 加载 LLM 配置失败: {}", e);
            LLMConfig {
                providers: HashMap::new(),
                roles: HashMap::new(),
            }
        })
    })
}

pub fn reload_config() -> Result<()> {
    let config = load_config()?;
    CONFIG
        .set(config)
        .map_err(|_| LLMError::Config("配置已初始化，无法重载".to_string()))?;
    Ok(())
}

pub fn get_provider_config(name: &str) -> Result<&'static ProviderConfig> {
    get_config()
        .providers
        .get(name)
        .ok_or_else(|| LLMError::ProviderNotFound(name.to_string()))
}

pub fn get_role_config(name: &str) -> Result<&'static RoleConfig> {
    get_config()
        .roles
        .get(name)
        .ok_or_else(|| LLMError::RoleNotFound(name.to_string()))
}
