use async_trait::async_trait;
use tokio::sync::mpsc;

use crate::config::{get_provider_config, get_role_config, ProviderConfig};
use crate::error::Result;
use crate::types::{CompletionResponse, Message, StreamChunk, ToolDefinition};

mod openai;
mod anthropic;
mod gemini;

#[async_trait]
pub trait Provider: Send + Sync {
    async fn complete(
        &self,
        model: &str,
        messages: &[Message],
        tools: &[ToolDefinition],
        max_tokens: Option<u32>,
        temperature: Option<f64>,
    ) -> Result<CompletionResponse>;

    async fn complete_stream(
        &self,
        model: &str,
        messages: &[Message],
        tools: &[ToolDefinition],
        max_tokens: Option<u32>,
        temperature: Option<f64>,
    ) -> Result<mpsc::Receiver<StreamChunk>>;

    fn name(&self) -> &str;
}

pub fn create_provider(provider_name: &str) -> Result<Box<dyn Provider>> {
    let config = get_provider_config(provider_name)?;
    match provider_name {
        "openai" => Ok(Box::new(openai::OpenAIProvider::new(config))),
        "anthropic" => Ok(Box::new(anthropic::AnthropicProvider::new(config))),
        "gemini" => Ok(Box::new(gemini::GeminiProvider::new(config))),
        _ => Err(crate::error::LLMError::Unsupported(format!(
            "未知的 provider: {}",
            provider_name
        ))),
    }
}

pub fn create_provider_for_role(role_name: &str) -> Result<(Box<dyn Provider>, String)> {
    let role_config = get_role_config(role_name)?;
    let provider = create_provider(&role_config.provider)?;
    Ok((provider, role_config.model.clone()))
}

fn build_headers(config: &ProviderConfig) -> reqwest::header::HeaderMap {
    let mut headers = reqwest::header::HeaderMap::new();
    if let Some(custom) = &config.headers {
        for (k, v) in custom {
            if let (Ok(name), Ok(value)) = (
                reqwest::header::HeaderName::from_bytes(k.as_bytes()),
                reqwest::header::HeaderValue::from_str(v),
            ) {
                headers.insert(name, value);
            }
        }
    }
    headers
}
