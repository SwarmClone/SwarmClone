use async_trait::async_trait;
use futures::StreamExt;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use tokio::sync::mpsc;

use crate::config::ProviderConfig;
use crate::error::{LLMError, Result};
use crate::provider::{build_headers, Provider};
use crate::types::{
    CompletionResponse, FunctionCall, Message, Role, StreamChunk, ToolCall, ToolDefinition, Usage,
};

pub struct AnthropicProvider {
    client: Client,
    base_url: String,
}

#[derive(Serialize)]
struct RequestBody {
    model: String,
    messages: Vec<RequestMessage>,
    #[serde(skip_serializing_if = "Option::is_none")]
    system: Option<String>,
    max_tokens: u32,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    tools: Vec<RequestTool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    temperature: Option<f64>,
    stream: bool,
}

#[derive(Serialize)]
struct RequestMessage {
    role: String,
    content: Vec<RequestContent>,
}

#[derive(Serialize)]
#[serde(tag = "type")]
enum RequestContent {
    #[serde(rename = "text")]
    Text { text: String },
    #[serde(rename = "tool_use")]
    ToolUse {
        id: String,
        name: String,
        input: serde_json::Value,
    },
    #[serde(rename = "tool_result")]
    ToolResult {
        tool_use_id: String,
        content: String,
    },
}

#[derive(Serialize)]
struct RequestTool {
    name: String,
    description: String,
    input_schema: serde_json::Value,
}

#[derive(Deserialize)]
struct ResponseBody {
    content: Vec<ResponseContent>,
    stop_reason: Option<String>,
    #[serde(default)]
    usage: Option<ResponseUsage>,
}

#[derive(Deserialize)]
struct ResponseContent {
    #[serde(rename = "type")]
    content_type: String,
    #[serde(default)]
    text: Option<String>,
    #[serde(default)]
    id: Option<String>,
    #[serde(default)]
    name: Option<String>,
    #[serde(default)]
    input: Option<serde_json::Value>,
}

#[derive(Deserialize)]
struct ResponseUsage {
    input_tokens: u32,
    output_tokens: u32,
}

#[derive(Deserialize)]
struct StreamEvent {
    #[serde(rename = "type")]
    event_type: String,
    #[serde(flatten)]
    data: serde_json::Value,
}

impl AnthropicProvider {
    pub fn new(config: &ProviderConfig) -> Self {
        let mut headers = build_headers(config);
        headers.insert("x-api-key", config.api_key.parse().expect("无效的 API key"));
        headers.insert("anthropic-version", "2023-06-01".parse().unwrap());
        headers.insert(
            reqwest::header::CONTENT_TYPE,
            "application/json".parse().unwrap(),
        );

        let client = Client::builder()
            .default_headers(headers)
            .build()
            .expect("构建 HTTP 客户端失败");

        Self {
            client,
            base_url: config.base_url.trim_end_matches('/').to_string(),
        }
    }

    fn convert_messages(messages: &[Message]) -> (Option<String>, Vec<RequestMessage>) {
        let mut system = None;
        let mut request_messages = Vec::new();

        for msg in messages {
            match msg.role {
                Role::System => {
                    system = msg.content.clone();
                }
                Role::User => {
                    let content = vec![RequestContent::Text {
                        text: msg.content.clone().unwrap_or_default(),
                    }];
                    request_messages.push(RequestMessage {
                        role: "user".to_string(),
                        content,
                    });
                }
                Role::Assistant => {
                    let mut content = Vec::new();
                    if let Some(text) = &msg.content {
                        content.push(RequestContent::Text { text: text.clone() });
                    }
                    if let Some(calls) = &msg.tool_calls {
                        for call in calls {
                            let input: serde_json::Value =
                                serde_json::from_str(&call.function.arguments)
                                    .unwrap_or(serde_json::Value::Object(serde_json::Map::new()));
                            content.push(RequestContent::ToolUse {
                                id: call.id.clone(),
                                name: call.function.name.clone(),
                                input,
                            });
                        }
                    }
                    if !content.is_empty() {
                        request_messages.push(RequestMessage {
                            role: "assistant".to_string(),
                            content,
                        });
                    }
                }
                Role::Tool => {
                    let content = vec![RequestContent::ToolResult {
                        tool_use_id: msg.tool_call_id.clone().unwrap_or_default(),
                        content: msg.content.clone().unwrap_or_default(),
                    }];
                    request_messages.push(RequestMessage {
                        role: "user".to_string(),
                        content,
                    });
                }
            }
        }

        (system, request_messages)
    }

    fn convert_tools(tools: &[ToolDefinition]) -> Vec<RequestTool> {
        tools
            .iter()
            .map(|t| RequestTool {
                name: t.function.name.clone(),
                description: t.function.description.clone(),
                input_schema: t.function.parameters.clone(),
            })
            .collect()
    }
}

#[async_trait]
impl Provider for AnthropicProvider {
    async fn complete(
        &self,
        model: &str,
        messages: &[Message],
        tools: &[ToolDefinition],
        max_tokens: Option<u32>,
        temperature: Option<f64>,
    ) -> Result<CompletionResponse> {
        let (system, request_messages) = Self::convert_messages(messages);

        let body = RequestBody {
            model: model.to_string(),
            messages: request_messages,
            system,
            max_tokens: max_tokens.unwrap_or(4096),
            tools: Self::convert_tools(tools),
            temperature,
            stream: false,
        };

        let url = format!("{}/v1/messages", self.base_url);
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

        let mut text_content = None;
        let mut tool_calls = Vec::new();

        for content in &body.content {
            match content.content_type.as_str() {
                "text" => {
                    text_content = content.text.clone();
                }
                "tool_use" => {
                    if let (Some(id), Some(name), Some(input)) =
                        (&content.id, &content.name, &content.input)
                    {
                        tool_calls.push(ToolCall {
                            id: id.clone(),
                            call_type: "function".to_string(),
                            function: FunctionCall {
                                name: name.clone(),
                                arguments: serde_json::to_string(input).unwrap_or_default(),
                            },
                        });
                    }
                }
                _ => {}
            }
        }

        Ok(CompletionResponse {
            content: text_content,
            tool_calls: if tool_calls.is_empty() {
                None
            } else {
                Some(tool_calls)
            },
            finish_reason: body.stop_reason,
            usage: body.usage.map(|u| Usage {
                prompt_tokens: u.input_tokens,
                completion_tokens: u.output_tokens,
                total_tokens: u.input_tokens + u.output_tokens,
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
        let (system, request_messages) = Self::convert_messages(messages);

        let body = RequestBody {
            model: model.to_string(),
            messages: request_messages,
            system,
            max_tokens: max_tokens.unwrap_or(4096),
            tools: Self::convert_tools(tools),
            temperature,
            stream: true,
        };

        let url = format!("{}/v1/messages", self.base_url);
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
                    if let Ok(event) = serde_json::from_str::<StreamEvent>(data) {
                        match event.event_type.as_str() {
                            "content_block_delta" => {
                                if let Some(delta) = event.data.get("delta") {
                                    if delta.get("type").and_then(|t| t.as_str())
                                        == Some("text_delta")
                                    {
                                        let text = delta
                                            .get("text")
                                            .and_then(|t| t.as_str())
                                            .unwrap_or("")
                                            .to_string();
                                        let _ = tx
                                            .send(StreamChunk {
                                                delta: text,
                                                finish_reason: None,
                                                tool_calls_delta: None,
                                            })
                                            .await;
                                    }
                                }
                            }
                            "message_delta" => {
                                if let Some(delta) = event.data.get("delta") {
                                    let stop = delta
                                        .get("stop_reason")
                                        .and_then(|s| s.as_str())
                                        .map(|s| s.to_string());
                                    let _ = tx
                                        .send(StreamChunk {
                                            delta: String::new(),
                                            finish_reason: stop,
                                            tool_calls_delta: None,
                                        })
                                        .await;
                                }
                            }
                            "message_stop" => {
                                return;
                            }
                            _ => {}
                        }
                    }
                }
            }
        });

        Ok(rx)
    }

    fn name(&self) -> &str {
        "anthropic"
    }
}
