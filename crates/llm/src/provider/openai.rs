use async_trait::async_trait;
use futures::StreamExt;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use tokio::sync::mpsc;

use crate::config::ProviderConfig;
use crate::error::{LLMError, Result};
use crate::provider::{build_headers, Provider};
use crate::types::{
    CompletionResponse, FunctionCall, Message, Role, StreamChunk, ToolCall, ToolCallDelta,
    ToolDefinition, Usage,
};

pub struct OpenAIProvider {
    client: Client,
    base_url: String
}

#[derive(Serialize)]
struct RequestBody {
    model: String,
    messages: Vec<RequestMessage>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    tools: Vec<RequestTool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    max_tokens: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    temperature: Option<f64>,
    stream: bool,
}

#[derive(Serialize)]
struct RequestMessage {
    role: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    content: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    tool_calls: Option<Vec<ToolCall>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    tool_call_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    name: Option<String>,
}

#[derive(Serialize)]
struct RequestTool {
    #[serde(rename = "type")]
    tool_type: String,
    function: RequestFunction,
}

#[derive(Serialize)]
struct RequestFunction {
    name: String,
    description: String,
    parameters: serde_json::Value,
}

#[derive(Deserialize)]
struct ResponseBody {
    choices: Vec<Choice>,
    #[serde(default)]
    usage: Option<ResponseUsage>,
}

#[derive(Deserialize)]
struct Choice {
    message: Option<ResponseMessage>,
    delta: Option<ResponseDelta>,
    finish_reason: Option<String>,
}

#[derive(Deserialize)]
struct ResponseMessage {
    content: Option<String>,
    #[serde(default)]
    tool_calls: Option<Vec<ResponseToolCall>>,
}

#[derive(Deserialize)]
struct ResponseDelta {
    content: Option<String>,
    #[serde(default)]
    tool_calls: Option<Vec<ResponseToolCallDelta>>,
}

#[derive(Deserialize)]
struct ResponseToolCall {
    id: String,
    #[serde(rename = "type")]
    call_type: String,
    function: ResponseFunction,
}

#[derive(Deserialize)]
struct ResponseFunction {
    name: String,
    arguments: String,
}

#[derive(Deserialize)]
struct ResponseToolCallDelta {
    index: usize,
    id: Option<String>,
    function: Option<ResponseFunctionDelta>,
}

#[derive(Deserialize)]
struct ResponseFunctionDelta {
    name: Option<String>,
    arguments: Option<String>,
}

#[derive(Deserialize)]
struct ResponseUsage {
    prompt_tokens: u32,
    completion_tokens: u32,
    total_tokens: u32,
}

impl OpenAIProvider {
    pub fn new(config: &ProviderConfig) -> Self {
        let mut headers = build_headers(config);
        headers.insert(
            reqwest::header::AUTHORIZATION,
            reqwest::header::HeaderValue::from_str(&format!("Bearer {}", config.api_key))
                .unwrap_or_else(|_| reqwest::header::HeaderValue::from_static("")),
        );
        headers.insert(
            reqwest::header::CONTENT_TYPE,
            reqwest::header::HeaderValue::from_static("application/json"),
        );

        let client = Client::builder()
            .default_headers(headers)
            .build()
            .expect("构建 HTTP 客户端失败");

        Self {
            client,
            base_url: config.base_url.trim_end_matches('/').to_string()
        }
    }

    fn convert_messages(messages: &[Message]) -> Vec<RequestMessage> {
        messages
            .iter()
            .map(|m| RequestMessage {
                role: match m.role {
                    Role::System => "system".to_string(),
                    Role::User => "user".to_string(),
                    Role::Assistant => "assistant".to_string(),
                    Role::Tool => "tool".to_string(),
                },
                content: m.content.clone(),
                tool_calls: m.tool_calls.clone(),
                tool_call_id: m.tool_call_id.clone(),
                name: m.name.clone(),
            })
            .collect()
    }

    fn convert_tools(tools: &[ToolDefinition]) -> Vec<RequestTool> {
        tools
            .iter()
            .map(|t| RequestTool {
                tool_type: t.tool_type.clone(),
                function: RequestFunction {
                    name: t.function.name.clone(),
                    description: t.function.description.clone(),
                    parameters: t.function.parameters.clone(),
                },
            })
            .collect()
    }
}

#[async_trait]
impl Provider for OpenAIProvider {
    async fn complete(
        &self,
        model: &str,
        messages: &[Message],
        tools: &[ToolDefinition],
        max_tokens: Option<u32>,
        temperature: Option<f64>,
    ) -> Result<CompletionResponse> {
        let body = RequestBody {
            model: model.to_string(),
            messages: Self::convert_messages(messages),
            tools: Self::convert_tools(tools),
            max_tokens,
            temperature,
            stream: false,
        };

        let url = format!("{}/chat/completions", self.base_url);
        let resp = self.client.post(&url).json(&body).send().await?;

        if !resp.status().is_success() {
            let status = resp.status().as_u16();
            let text = resp.text().await.unwrap_or_default();
            return Err(LLMError::Api {
                status,
                message: text,
            });
        }

        let body: ResponseBody = resp.json().await?;
        let choice = body.choices.into_iter().next().ok_or_else(|| {
            LLMError::Internal("响应中没有 choices".to_string())
        })?;

        let message = choice.message.ok_or_else(|| {
            LLMError::Internal("响应中没有 message".to_string())
        })?;

        let tool_calls = message.tool_calls.map(|calls| {
            calls
                .into_iter()
                .map(|tc| ToolCall {
                    id: tc.id,
                    call_type: tc.call_type,
                    function: FunctionCall {
                        name: tc.function.name,
                        arguments: tc.function.arguments,
                    },
                })
                .collect()
        });

        Ok(CompletionResponse {
            content: message.content,
            tool_calls,
            finish_reason: choice.finish_reason,
            usage: body.usage.map(|u| Usage {
                prompt_tokens: u.prompt_tokens,
                completion_tokens: u.completion_tokens,
                total_tokens: u.total_tokens,
            }),
        })
    }

    async fn complete_stream(
        &self,
        model: &str,
        messages: &[Message],
        tools: &[ToolDefinition],
        max_tokens: Option<u32>,
        temperature: Option<f64>,
    ) -> Result<mpsc::Receiver<StreamChunk>> {
        let body = RequestBody {
            model: model.to_string(),
            messages: Self::convert_messages(messages),
            tools: Self::convert_tools(tools),
            max_tokens,
            temperature,
            stream: true,
        };

        let url = format!("{}/chat/completions", self.base_url);
        let resp = self.client.post(&url).json(&body).send().await?;

        if !resp.status().is_success() {
            let status = resp.status().as_u16();
            let text = resp.text().await.unwrap_or_default();
            return Err(LLMError::Api {
                status,
                message: text,
            });
        }

        let (tx, rx) = mpsc::channel(256);

        tokio::spawn(async move {
            let mut stream = resp.bytes_stream();
            let mut buffer = String::new();

            while let Some(chunk_result) = stream.next().await {
                let bytes = match chunk_result {
                    Ok(b) => b,
                    Err(_) => break,
                };

                buffer.push_str(&String::from_utf8_lossy(&bytes));

                while let Some(line_end) = buffer.find('\n') {
                    let line = buffer[..line_end].trim().to_string();
                    buffer = buffer[line_end + 1..].to_string();

                    if line.is_empty() || !line.starts_with("data: ") {
                        continue;
                    }

                    let data = &line[6..];
                    if data == "[DONE]" {
                        let _ = tx
                            .send(StreamChunk {
                                delta: String::new(),
                                finish_reason: Some("stop".to_string()),
                                tool_calls_delta: None,
                            })
                            .await;
                        return;
                    }

                    if let Ok(choice) = serde_json::from_str::<Choice>(data) {
                        let delta = choice.delta.unwrap_or(ResponseDelta {
                            content: None,
                            tool_calls: None,
                        });

                        let tool_calls_delta = delta.tool_calls.map(|deltas| {
                            deltas
                                .into_iter()
                                .map(|d| ToolCallDelta {
                                    index: d.index,
                                    id: d.id,
                                    function_name: d.function.as_ref().and_then(|f| f.name.clone()),
                                    function_arguments_delta: d
                                        .function
                                        .as_ref()
                                        .and_then(|f| f.arguments.clone()),
                                })
                                .collect()
                        });

                        let _ = tx
                            .send(StreamChunk {
                                delta: delta.content.unwrap_or_default(),
                                finish_reason: choice.finish_reason,
                                tool_calls_delta,
                            })
                            .await;
                    }
                }
            }
        });

        Ok(rx)
    }

    fn name(&self) -> &str {
        "openai"
    }
}
