use std::collections::HashMap;
use std::sync::Arc;

use tokio::sync::mpsc;

use crate::config::{get_config, get_role_config, RoleConfig};
use crate::error::{LLMError, Result};
use crate::provider::{create_provider, Provider};
use crate::types::{
    CompletionResponse, Message, StreamChunk, ToolDefinition,
};

#[async_trait::async_trait]
pub trait ToolExecutor: Send + Sync {
    async fn execute(&self, name: &str, arguments: &str) -> Result<String>;
}

pub struct Session {
    role_name: String,
    role_config: RoleConfig,
    provider: Box<dyn Provider>,
    messages: Vec<Message>,
    tools: Vec<ToolDefinition>,
    tool_executor: Option<Arc<dyn ToolExecutor>>,
    max_tool_rounds: usize,
}

impl Session {
    pub fn new(role_name: &str) -> Result<Self> {
        let role_config = get_role_config(role_name)?.clone();
        let provider = create_provider(&role_config.provider)?;

        let mut messages = Vec::new();
        if let Some(system_prompt) = &role_config.system_prompt {
            messages.push(Message::system(system_prompt));
        }

        Ok(Self {
            role_name: role_name.to_string(),
            role_config,
            provider,
            messages,
            tools: Vec::new(),
            tool_executor: None,
            max_tool_rounds: 10,
        })
    }

    pub fn with_tools(mut self, tools: Vec<ToolDefinition>) -> Self {
        self.tools = tools;
        self
    }

    pub fn with_tool_executor(mut self, executor: Arc<dyn ToolExecutor>) -> Self {
        self.tool_executor = Some(executor);
        self
    }

    pub fn with_max_tool_rounds(mut self, rounds: usize) -> Self {
        self.max_tool_rounds = rounds;
        self
    }

    pub fn add_message(&mut self, message: Message) {
        self.messages.push(message);
    }

    pub fn clear(&mut self) {
        self.messages.clear();
        if let Some(system_prompt) = &self.role_config.system_prompt {
            self.messages.push(Message::system(system_prompt));
        }
    }

    pub fn messages(&self) -> &[Message] {
        &self.messages
    }

    pub fn role_name(&self) -> &str {
        &self.role_name
    }

    pub async fn chat(&mut self, input: &str) -> Result<String> {
        self.messages.push(Message::user(input));
        self.run_completion_loop().await
    }

    pub async fn chat_with_response(&mut self, input: &str) -> Result<CompletionResponse> {
        self.messages.push(Message::user(input));
        self.run_completion_once().await
    }

    pub async fn chat_stream(&mut self, input: &str) -> Result<mpsc::Receiver<StreamChunk>> {
        self.messages.push(Message::user(input));

        let messages = self.messages.clone();
        let tools = self.tools.clone();
        let model = self.role_config.model.clone();

        let rx = self
            .provider
            .complete_stream(
                &model,
                &messages,
                &tools,
                self.role_config.max_tokens,
                self.role_config.temperature,
            )
            .await?;

        Ok(rx)
    }

    async fn run_completion_loop(&mut self) -> Result<String> {
        for _ in 0..self.max_tool_rounds {
            let response = self.run_completion_once().await?;

            if let Some(tool_calls) = &response.tool_calls {
                if let Some(executor) = &self.tool_executor {
                    self.messages.push(Message::assistant_with_tool_calls(
                        response.content.clone(),
                        tool_calls.clone(),
                    ));

                    for call in tool_calls {
                        let result = executor.execute(&call.function.name, &call.function.arguments).await;
                        let result_content = match result {
                            Ok(r) => r,
                            Err(e) => format!("工具执行错误: {}", e),
                        };
                        self.messages
                            .push(Message::tool(&call.id, result_content));
                    }

                    continue;
                }
            }

            if let Some(content) = response.content {
                self.messages.push(Message::assistant(&content));
                return Ok(content);
            }

            return Ok(String::new());
        }

        Err(LLMError::Internal(format!(
            "工具调用超过最大轮次 ({})",
            self.max_tool_rounds
        )))
    }

    async fn run_completion_once(&mut self) -> Result<CompletionResponse> {
        self.provider
            .complete(
                &self.role_config.model,
                &self.messages,
                &self.tools,
                self.role_config.max_tokens,
                self.role_config.temperature,
            )
            .await
    }
}

pub struct SessionManager {
    sessions: HashMap<String, Session>,
}

impl SessionManager {
    pub fn new() -> Self {
        Self {
            sessions: HashMap::new(),
        }
    }

    pub fn create_session(&mut self, role_name: &str) -> Result<()> {
        let session = Session::new(role_name)?;
        self.sessions.insert(role_name.to_string(), session);
        Ok(())
    }

    pub fn get(&self, role_name: &str) -> Option<&Session> {
        self.sessions.get(role_name)
    }

    pub fn get_mut(&mut self, role_name: &str) -> Option<&mut Session> {
        self.sessions.get_mut(role_name)
    }

    pub fn get_or_create(&mut self, role_name: &str) -> Result<&mut Session> {
        if !self.sessions.contains_key(role_name) {
            self.create_session(role_name)?;
        }
        Ok(self.sessions.get_mut(role_name).unwrap())
    }

    pub fn remove(&mut self, role_name: &str) -> Option<Session> {
        self.sessions.remove(role_name)
    }

    pub fn list_roles(&self) -> Vec<&str> {
        self.sessions.keys().map(|s| s.as_str()).collect()
    }
}

impl Default for SessionManager {
    fn default() -> Self {
        Self::new()
    }
}

pub fn available_roles() -> Vec<String> {
    get_config().roles.keys().cloned().collect()
}

pub fn available_providers() -> Vec<String> {
    get_config().providers.keys().cloned().collect()
}
