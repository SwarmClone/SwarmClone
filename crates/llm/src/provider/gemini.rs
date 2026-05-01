use async_trait::async_trait;
use futures::StreamExt;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use tokio::sync::mpsc;

use crate::config::ProviderConfig;
use crate::error::{LLMError, Result};
use crate::provider::Provider;
use crate::types::{
    CompletionResponse, FunctionCall, Message, Role, StreamChunk, ToolCall, ToolDefinition, Usage,
};

pub struct GeminiProvider {
    client: Client,
    base_url: String,
    api_key: String,
}

#[derive(Serialize)]
struct RequestBody {
    contents: Vec<RequestContent>,
    #[serde(skip_serializing_if = "Option::is_none")]
    tools: Option<Vec<RequestTool>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    generation_config: Option<GenerationConfig>,
    #[serde(skip_serializing_if = "Option::is_none")]
    system_instruction: Option<SystemInstruction>,
}

#[derive(Serialize)]
struct RequestContent {
    role: String,
    parts: Vec<RequestPart>,
}

#[derive(Serialize)]
#[serde(tag = "type")]
enum RequestPart {
    #[serde(rename = "text")]
    Text { text: String },
    #[serde(rename = "functionCall")]
    FunctionCall {
        name: String,
        args: serde_json::Value,
    },
    #[serde(rename = "functionResponse")]
    FunctionResponse {
        name: String,
        response: serde_json::Value,
    },
}

#[derive(Serialize)]
struct RequestTool {
    function_declarations: Vec<FunctionDeclaration>,
}

#[derive(Serialize)]
struct FunctionDeclaration {
    name: String,
    description: String,
    parameters: serde_json::Value,
}

#[derive(Serialize)]
struct GenerationConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    max_output_tokens: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    temperature: Option<f64>,
}

#[derive(Serialize)]
struct SystemInstruction {
    parts: Vec<RequestPart>,
}

#[derive(Deserialize)]
struct ResponseBody {
    candidates: Vec<Candidate>,
    #[serde(default)]
    usage_metadata: Option<UsageMetadata>,
}

#[derive(Deserialize)]
struct Candidate {
    content: ResponseContent,
    finish_reason: Option<String>,
}

#[derive(Deserialize)]
struct ResponseContent {
    parts: Vec<ResponsePart>,
}

#[derive(Deserialize)]
struct ResponsePart {
    #[serde(default)]
    text: Option<String>,
    #[serde(default)]
    function_call: Option<ResponseFunctionCall>,
}

#[derive(Deserialize)]
struct ResponseFunctionCall {
    name: String,
    args: serde_json::Value,
}

#[derive(Deserialize)]
struct UsageMetadata {
    prompt_token_count: u32,
    candidates_token_count: u32,
    total_token_count: u32,
}

impl GeminiProvider {
    pub fn new(config: &ProviderConfig) -> Self {
        let client = Client::builder().build().expect("构建 HTTP 客户端失败");

        Self {
            client,
            base_url: config.base_url.trim_end_matches('/').to_string(),
            api_key: config.api_key.clone(),
        }
    }

    fn convert_messages(messages: &[Message]) -> (Option<String>, Vec<RequestContent>) {
        let mut system = None;
        let mut contents = Vec::new();

        for msg in messages {
            match msg.role {
                Role::System => {
                    system = msg.content.clone();
                }
                Role::User => {
                    contents.push(RequestContent {
                        role: "user".to_string(),
                        parts: vec![RequestPart::Text {
                            text: msg.content.clone().unwrap_or_default(),
                        }],
                    });
                }
                Role::Assistant => {
                    let mut parts = Vec::new();
                    if let Some(text) = &msg.content {
                        parts.push(RequestPart::Text { text: text.clone() });
                    }
                    if let Some(calls) = &msg.tool_calls {
                        for call in calls {
                            let args: serde_json::Value =
                                serde_json::from_str(&call.function.arguments)
                                    .unwrap_or(serde_json::Value::Object(serde_json::Map::new()));
                            parts.push(RequestPart::FunctionCall {
                                name: call.function.name.clone(),
                                args,
                            });
                        }
                    }
                    if !parts.is_empty() {
                        contents.push(RequestContent {
                            role: "model".to_string(),
                            parts,
                        });
                    }
                }
                Role::Tool => {
                    let result_content: serde_json::Value =
                        serde_json::from_str(&msg.content.clone().unwrap_or_default()).unwrap_or(
                            serde_json::Value::String(msg.content.clone().unwrap_or_default()),
                        );
                    contents.push(RequestContent {
                        role: "function".to_string(),
                        parts: vec![RequestPart::FunctionResponse {
                            name: msg.name.clone().unwrap_or_default(),
                            response: result_content,
                        }],
                    });
                }
            }
        }

        (system, contents)
    }

    fn convert_tools(tools: &[ToolDefinition]) -> Vec<RequestTool> {
        if tools.is_empty() {
            return Vec::new();
        }

        let declarations = tools
            .iter()
            .map(|t| FunctionDeclaration {
                name: t.function.name.clone(),
                description: t.function.description.clone(),
                parameters: t.function.parameters.clone(),
            })
            .collect();

        vec![RequestTool {
            function_declarations: declarations,
        }]
    }
}

#[async_trait]
impl Provider for GeminiProvider {
    async fn complete(
        &self,
        model: &str,
        messages: &[Message],
        tools: &[ToolDefinition],
        max_tokens: Option<u32>,
        temperature: Option<f64>,
    ) -> Result<CompletionResponse> {
        let (system, contents) = Self::convert_messages(messages);

        let body = RequestBody {
            contents,
            tools: {
                let t = Self::convert_tools(tools);
                if t.is_empty() { None } else { Some(t) }
            },
            generation_config: Some(GenerationConfig {
                max_output_tokens: max_tokens,
                temperature,
            }),
            system_instruction: system.map(|s| SystemInstruction {
                parts: vec![RequestPart::Text { text: s }],
            }),
        };

        let url = format!(
            "{}/models/{}:generateContent?key={}",
            self.base_url, model, self.api_key
        );
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
        let candidate = body
            .candidates
            .into_iter()
            .next()
            .ok_or_else(|| LLMError::Internal("响应中没有 candidates".to_string()))?;

        let mut text_content = None;
        let mut tool_calls = Vec::new();

        for part in &candidate.content.parts {
            if let Some(text) = &part.text {
                text_content = Some(text.clone());
            }
            if let Some(fc) = &part.function_call {
                tool_calls.push(ToolCall {
                    id: uuid(),
                    call_type: "function".to_string(),
                    function: FunctionCall {
                        name: fc.name.clone(),
                        arguments: serde_json::to_string(&fc.args).unwrap_or_default(),
                    },
                });
            }
        }

        Ok(CompletionResponse {
            content: text_content,
            tool_calls: if tool_calls.is_empty() {
                None
            } else {
                Some(tool_calls)
            },
            finish_reason: candidate.finish_reason,
            usage: body.usage_metadata.map(|u| Usage {
                prompt_tokens: u.prompt_token_count,
                completion_tokens: u.candidates_token_count,
                total_tokens: u.total_token_count,
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
        let (system, contents) = Self::convert_messages(messages);

        let body = RequestBody {
            contents,
            tools: {
                let t = Self::convert_tools(tools);
                if t.is_empty() { None } else { Some(t) }
            },
            generation_config: Some(GenerationConfig {
                max_output_tokens: max_tokens,
                temperature,
            }),
            system_instruction: system.map(|s| SystemInstruction {
                parts: vec![RequestPart::Text { text: s }],
            }),
        };

        let url = format!(
            "{}/models/{}:streamGenerateContent?alt=sse&key={}",
            self.base_url, model, self.api_key
        );
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
                    if let Ok(resp) = serde_json::from_str::<ResponseBody>(data) {
                        if let Some(candidate) = resp.candidates.into_iter().next() {
                            let mut delta_text = String::new();
                            for part in &candidate.content.parts {
                                if let Some(text) = &part.text {
                                    delta_text.push_str(text);
                                }
                            }

                            let finish = candidate.finish_reason.clone();
                            let _ = tx
                                .send(StreamChunk {
                                    delta: delta_text,
                                    finish_reason: finish,
                                    tool_calls_delta: None,
                                })
                                .await;
                        }
                    }
                }
            }
        });

        Ok(rx)
    }

    fn name(&self) -> &str {
        "gemini"
    }
}

fn uuid() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let t = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    format!("call_{:x}", t)
}
