use thiserror::Error;

#[derive(Debug, Error)]
pub enum SpeechError {
    #[error("配置错误: {0}")]
    Config(String),

    #[error("WebSocket 错误: {0}")]
    WebSocket(#[from] tokio_tungstenite::tungstenite::Error),

    #[error("HTTP 头错误: {0}")]
    Header(#[from] http::header::InvalidHeaderValue),

    #[error("JSON 错误: {0}")]
    Json(#[from] serde_json::Error),

    #[error("语音服务错误: {0}")]
    Service(String),

    #[error("内部错误: {0}")]
    Internal(String),
}

pub type Result<T> = std::result::Result<T, SpeechError>;
