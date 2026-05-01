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

    // ========== LLM 模块测试 ==========
    log::info!("main", "开始 LLM 模块测试...");
    test_types();
    test_message_construction();
    test_tool_definition();
    test_available_roles();
    log::info!("main", "LLM 模块测试完成");
}

fn test_types() {
    use llm::types::*;

    // 测试 Role 枚举序列化/反序列化
    let role = Role::User;
    let json = serde_json::to_string(&role).unwrap();
    assert_eq!(json, "\"user\"");
    let deserialized: Role = serde_json::from_str(&json).unwrap();
    assert_eq!(deserialized, Role::User);
    log::info!("test_types", "Role 序列化/反序列化: 通过");

    // 测试 FunctionCall
    let fc = FunctionCall {
        name: "test_func".to_string(),
        arguments: "{\"key\":\"value\"}".to_string(),
    };
    let json = serde_json::to_string(&fc).unwrap();
    assert!(json.contains("test_func"));
    log::info!("test_types", "FunctionCall 序列化: 通过");

    // 测试 ToolCall
    let tc = ToolCall {
        id: "call_123".to_string(),
        call_type: "function".to_string(),
        function: fc,
    };
    let json = serde_json::to_string(&tc).unwrap();
    assert!(json.contains("call_123"));
    log::info!("test_types", "ToolCall 序列化: 通过");

    // 测试 Usage 默认值
    let usage = Usage::default();
    assert_eq!(usage.prompt_tokens, 0);
    assert_eq!(usage.completion_tokens, 0);
    assert_eq!(usage.total_tokens, 0);
    log::info!("test_types", "Usage 默认值: 通过");

    // 测试 CompletionResponse
    let resp = CompletionResponse {
        content: Some("hello".to_string()),
        tool_calls: None,
        finish_reason: Some("stop".to_string()),
        usage: Some(Usage {
            prompt_tokens: 10,
            completion_tokens: 5,
            total_tokens: 15,
        }),
    };
    assert_eq!(resp.content.unwrap(), "hello");
    assert!(resp.tool_calls.is_none());
    log::info!("test_types", "CompletionResponse 构造: 通过");

    // 测试 StreamChunk
    let chunk = StreamChunk {
        delta: "world".to_string(),
        finish_reason: None,
        tool_calls_delta: None,
    };
    assert_eq!(chunk.delta, "world");
    log::info!("test_types", "StreamChunk 构造: 通过");

    // 测试 ToolCallDelta
    let delta = ToolCallDelta {
        index: 0,
        id: Some("call_456".to_string()),
        function_name: Some("my_func".to_string()),
        function_arguments_delta: Some("{\"a\":".to_string()),
    };
    assert_eq!(delta.index, 0);
    log::info!("test_types", "ToolCallDelta 构造: 通过");
}

fn test_message_construction() {
    use llm::types::*;

    // 测试 system 消息
    let msg = Message::system("你是一个助手");
    assert_eq!(msg.role, Role::System);
    assert_eq!(msg.content.as_deref(), Some("你是一个助手"));
    assert!(msg.tool_calls.is_none());
    log::info!("test_message", "Message::system: 通过");

    // 测试 user 消息
    let msg = Message::user("你好");
    assert_eq!(msg.role, Role::User);
    assert_eq!(msg.content.as_deref(), Some("你好"));
    log::info!("test_message", "Message::user: 通过");

    // 测试 assistant 消息
    let msg = Message::assistant("回复内容");
    assert_eq!(msg.role, Role::Assistant);
    assert_eq!(msg.content.as_deref(), Some("回复内容"));
    log::info!("test_message", "Message::assistant: 通过");

    // 测试 tool 消息
    let msg = Message::tool("call_789", "执行结果");
    assert_eq!(msg.role, Role::Tool);
    assert_eq!(msg.tool_call_id.as_deref(), Some("call_789"));
    assert_eq!(msg.content.as_deref(), Some("执行结果"));
    log::info!("test_message", "Message::tool: 通过");

    // 测试 assistant_with_tool_calls
    let tool_calls = vec![ToolCall {
        id: "call_abc".to_string(),
        call_type: "function".to_string(),
        function: FunctionCall {
            name: "get_weather".to_string(),
            arguments: "{\"city\":\"北京\"}".to_string(),
        },
    }];
    let msg = Message::assistant_with_tool_calls(Some("让我查一下".to_string()), tool_calls);
    assert_eq!(msg.role, Role::Assistant);
    assert_eq!(msg.content.as_deref(), Some("让我查一下"));
    assert!(msg.tool_calls.is_some());
    assert_eq!(msg.tool_calls.as_ref().unwrap().len(), 1);
    assert_eq!(msg.tool_calls.as_ref().unwrap()[0].function.name, "get_weather");
    log::info!("test_message", "Message::assistant_with_tool_calls: 通过");

    // 测试 Message 序列化/反序列化
    let msg = Message::user("测试消息");
    let json = serde_json::to_string(&msg).unwrap();
    let deserialized: Message = serde_json::from_str(&json).unwrap();
    assert_eq!(deserialized.role, Role::User);
    assert_eq!(deserialized.content.as_deref(), Some("测试消息"));
    log::info!("test_message", "Message 序列化/反序列化: 通过");
}

fn test_tool_definition() {
    use llm::types::*;

    // 测试 ToolDefinition 构造
    let tool = ToolDefinition::function(
        "get_weather",
        "获取指定城市的天气信息",
        serde_json::json!({
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市名称"
                }
            },
            "required": ["city"]
        }),
    );

    assert_eq!(tool.tool_type, "function");
    assert_eq!(tool.function.name, "get_weather");
    assert_eq!(tool.function.description, "获取指定城市的天气信息");
    assert!(tool.function.parameters.is_object());
    log::info!("test_tool", "ToolDefinition 构造: 通过");

    // 测试 ToolDefinition 序列化
    let json = serde_json::to_string(&tool).unwrap();
    assert!(json.contains("get_weather"));
    assert!(json.contains("获取指定城市的天气信息"));
    log::info!("test_tool", "ToolDefinition 序列化: 通过");
}

fn test_available_roles() {
    let roles = llm::session::available_roles();
    log::info!("test_roles", "可用角色: {:?}", roles);

    let providers = llm::session::available_providers();
    log::info!("test_roles", "可用 Provider: {:?}", providers);
}
