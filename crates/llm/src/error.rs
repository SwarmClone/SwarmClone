use thiserror::Error;

#[derive(Error, Debug)]
pub enum LLMError {
    #[error("配置错误: {0}")]
    Config(String),

    #[error("Provider '{0}' 未找到")]
    ProviderNotFound(String),

    #[error("角色 '{0}' 未找到")]
    RoleNotFound(String),

    #[error("HTTP 请求失败: {0}")]
    Http(#[from] reqwest::Error),

    #[error("JSON 序列化/反序列化失败: {0}")]
    Json(#[from] serde_json::Error),

    #[error("API 错误 ({status}): {message}")]
    Api { status: u16, message: String },

    #[error("流式响应解析失败: {0}")]
    StreamParse(String),

    #[error("不支持的操作: {0}")]
    Unsupported(String),

    #[error("内部错误: {0}")]
    Internal(String),
}

pub type Result<T> = std::result::Result<T, LLMError>;
