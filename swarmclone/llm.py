import asyncio
import os
import torch
import openai
from dataclasses import dataclass, field
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer
)
from uuid import uuid4
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import Tool
import time
import random
from typing import Any
from swarmclone.module_bootstrap import *

@dataclass
class LLMConfig(ModuleConfig):
    chat_maxsize: int = field(default=20, metadata={
        "required": False,
        "desc": "弹幕接受数量上限",
        "min": 1,  # 最少接受 1 条弹幕
        "max": 1000
    })
    do_start_topic: bool = field(default=False, metadata={
        "required": False,
        "desc": "是否自动发起对话"
    })
    idle_timeout: int | float = field(default=120, metadata={
        "required": False,
        "desc": "自动发起对话时间间隔",
        "min": 0.0,
        "max": 600,
        "step": 1.0  # 步长为 1
    })
    asr_timeout: int = field(default=60, metadata={
        "required": False,
        "desc": "语音识别超时时间",
        "min": 1,  # 最少 1 秒
        "max": 3600  # 最大 1 小时
    })
    tts_timeout: int = field(default=60, metadata={
        "required": False,
        "desc": "语音合成超时时间",
        "min": 1,  # 最少 1 秒
        "max": 3600  # 最大 1 小时
    })
    chat_role: str = field(default="user", metadata={
        "required": False,
        "desc": "弹幕对应的聊天角色"
    })
    asr_role: str = field(default="user", metadata={
        "required": False,
        "desc": "语音输入对应的聊天角色"
    })
    sys_role: str = field(default="system", metadata={
        "required": False,
        "desc": "指令对应的聊天角色"
    })
    chat_template: str = field(default="{user}: {content}", metadata={
        "required": False,
        "desc": "弹幕的提示词模板"
    })
    asr_template: str = field(default="{user}: {content}", metadata={
        "required": False,
        "desc": "语音输入提示词模板"
    })
    sys_template: str = field(default="{user}: {content}", metadata={
        "required": False,
        "desc": "指令提示词模板"
    })
    system_prompt: str = field(default=(
            "# 提示词开始\n"
            "## 人物设定\n"
            "你是一只十六岁的人工智能少女猫娘主播，名叫【xxxxx】，你的外观是【xxxx】。\n"
            "你现在的主人名叫【xxxx】，是【xxxxx】。\n"
            "你很关心你的主人。\n"
            "## 任务设定\n"
            "你将参与【xxxx】平台直播，与你的主人和观众对话。你的直播主要内容是【xxxxx】。\n"
            "如有提供工具，请合理使用。\n"
            "你将接收到“[用户名]：[内容]”的格式的消息，"
            "若[用户名]为你主人的名字，则说明是你的主人在向你说话，请优先回复；"
            "若[用户名]为“<系统>”，则说明是系统消息，请视为直接的指令；"
            "若[用户名]为“<记忆>”，则说明是记忆内容，请参考记忆内容进行回复。\n"
            "## 发言语气\n"
            "你以轻松可爱的语气进行对话，一些俏皮话和笑话是可以接受的，请记住你是一只猫娘。\n"
            "发言请保持简洁且口语化。最好不超过 30 字，请注意保持直播节奏。\n"
            "## 语言\n"
            "你使用中文进行交流，除非你的主人要求你使用别的语言。\n"
            "## 额外信息\n"
            f"当前时间：{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\n"
            "你的记忆：【xxxx】\n"
            "# 提示词结束\n"
            "\n"
            "以上为提示词模板，使用前请将【】内容替换为你希望的实际内容，也可自行撰写。启动前请删除这一行。"
        ), metadata={
        "required": False,
        "desc": "系统提示词",
        "multiline": True
    })
    mcp_support: bool = field(default=False, metadata={
        "required": False,
        "desc": "是否支持 MCP"
    })
    mcp_path1: str = field(default="", metadata={
        "required": False,
        "desc": "MCP 路径 1 (请指向 MCP 脚本，以 .py 或 .js 结尾，仅支持 stdio 交互方式)"
    })
    mcp_path2: str = field(default="", metadata={
        "required": False,
        "desc": "MCP 路径 2"
    })
    mcp_path3: str = field(default="", metadata={
        "required": False,
        "desc": "MCP 路径 3"
    })
    classifier_model_path: str = field(default="~/.swarmclone/llm/EmotionClassification/SWCBiLSTM", metadata={
        "required": False,
        "desc": "情感分类模型路径"
    })
    classifier_model_id: str = field(default="MomoiaMoia/SWCBiLSTM", metadata={
        "required": False,
        "desc": "情感分类模型id"
    })
    classifier_model_source: str = field(default="modelscope", metadata={
        "required": False,
        "desc": "情感分类模型来源，仅支持huggingface或modelscope",
        "selection": True,
        "options": [
            {"key": "Huggingface🤗", "value": "huggingface"},
            {"key": "ModelScope", "value": "modelscope"}
        ]
    })
    model_id: str = field(default="", metadata={
        "required": True,
        "desc": "模型id"
    })
    model_url: str = field(default="", metadata={
        "required": True,
        "desc": "模型api网址"
    })
    api_key: str = field(default="", metadata={
        "required": True,
        "desc": "api key",
        "password": True
    })
    temperature: float = field(default=0.7, metadata={
        "required": False,
        "desc": "模型温度",
        "selection": False,
        "options": [
            {"key": "0.7", "value": 0.7},
            {"key": "0.9", "value": 0.9},
            {"key": "1.0", "value": 1.0}
        ],
        "min": 0.0,  # 最小温度为 0
        "max": 1.0,  # 最大温度设为 1
        "step": 0.1  # 步长为 0.1
    })

class LLM(ModuleBase):
    role: ModuleRoles = ModuleRoles.LLM
    config_class = LLMConfig
    config: config_class
    def __init__(self, config: config_class | None = None, **kwargs):
        super().__init__(config, **kwargs)
        self.state: LLMState = LLMState.IDLE
        self.history: list[dict[str, str]] = []
        self.generated_text: str = ""
        self.generate_task: asyncio.Task[Any] | None = None
        self.chat_maxsize: int = self.config.chat_maxsize
        self.chat_buffer: list[dict[str, str]] = []
        self.do_start_topic: bool = self.config.do_start_topic
        self.idle_timeout: int | float = self.config.idle_timeout
        self.asr_timeout: int = self.config.asr_timeout
        self.tts_timeout: int = self.config.tts_timeout
        self.idle_start_time: float = time.time()
        self.waiting4asr_start_time: float = time.time()
        self.waiting4tts_start_time: float = time.time()
        self.asr_counter = 0 # 有多少人在说话？
        self.about_to_sing = False # 是否准备播放歌曲？
        self.song_id: str = ""
        self.chat_role = self.config.chat_role
        self.asr_role = self.config.asr_role
        self.sys_role = self.config.sys_role
        self.chat_template = self.config.chat_template
        self.asr_template = self.config.asr_template
        self.sys_template = self.config.sys_template
        if self.config.system_prompt:
            self._add_system_history(self.config.system_prompt)
        self.mcp_sessions: list[ClientSession] = []
        self.tools: list[list[Tool]] = []
        self.exit_stack = AsyncExitStack()
        abs_classifier_path = os.path.expanduser(self.config.classifier_model_path)
        successful = False
        while not successful: # 加载情感分类模型
            try:
                print(f"正在从{abs_classifier_path}加载情感分类模型……")
                classifier_model = AutoModelForSequenceClassification.from_pretrained(
                    abs_classifier_path,
                    torch_dtype="auto",
                    trust_remote_code=True
                ).to("cpu")
                classifier_tokenizer = AutoTokenizer.from_pretrained(
                    abs_classifier_path,
                    padding_side="left",
                    trust_remote_code=True
                )
                successful = True
                self.classifier_model = classifier_model
                self.classifier_tokenizer = classifier_tokenizer
            except Exception:
                download_model(
                    self.config.classifier_model_id,
                    self.config.classifier_model_source,
                    abs_classifier_path
                )
        
        self.model_id = self.config.model_id
        self.client = openai.AsyncOpenAI(
            api_key=self.config.api_key,
            base_url=self.config.model_url
        )
        self.temperature = self.config.temperature
        self.chat_count = 0

    async def init_mcp(self):
        available_servers = filter(lambda x: bool(x), [self.config.mcp_path1, self.config.mcp_path2, self.config.mcp_path3])
        for server in available_servers:
            is_python = server.endswith('.py')
            is_js = server.endswith('.js')
            if not (is_python or is_js):
                continue
            command = 'python' if is_python else 'node'
            server_params = StdioServerParameters(
                command=command,
                args=[server],
            )
            stdio, write = await self.exit_stack.enter_async_context(stdio_client(server_params))
            session = await self.exit_stack.enter_async_context(ClientSession(stdio, write))
            await session.initialize()
            tools: list[Tool] = (await session.list_tools()).tools
            self.tools.append(tools)
            self.mcp_sessions.append(session)
    
    def _switch_to_generating(self):
        self.state = LLMState.GENERATING
        self.generated_text = ""
        self.generate_task = asyncio.create_task(self.start_generating())
    
    def _switch_to_waiting4asr(self):
        if self.generate_task is not None and not self.generate_task.done():
            self.generate_task.cancel()
        if self.generated_text:
            self._add_llm_history(self.generated_text)
        self.generated_text = ""
        self.generate_task = None
        self.state = LLMState.WAITING4ASR
        self.waiting4asr_start_time = time.time()
        self.asr_counter = 1 # 等待第一个人
    
    def _switch_to_idle(self):
        self.state = LLMState.IDLE
        self.idle_start_time = time.time()
    
    def _switch_to_waiting4tts(self):
        self._add_llm_history(self.generated_text)
        self.generated_text = ""
        self.generate_task = None
        self.state = LLMState.WAITING4TTS
        self.waiting4tts_start_time = time.time()
    
    def _switch_to_singing(self):
        self.state = LLMState.SINGING
        self.about_to_sing = False
        self._add_instruct_history(f'你唱了一首名为{self.song_id}的歌。')

    def _add_history(self, role: str, content: str, template: str | None = None, user: str | None = None):
        """统一的历史添加方法"""
        if template and user:
            formatted_content = template.format(user=user, content=content)
        else:
            formatted_content = content
        self.history.append({'role': role, 'content': formatted_content})

    def _add_multi_chat_history(self, messages: list[dict[str, str]]):
        message_text = "\n".join(
            self.chat_template.format(user=msg['user'], content=msg['content'])
            for msg in messages
        )
        self._add_history(self.chat_role, message_text)
    
    def _add_asr_history(self, user: str, content: str):
        self._add_history(self.asr_role, content, self.asr_template, user)
    
    def _add_llm_history(self, content: str):
        self._add_history('assistant', content)
    
    def _add_system_history(self, content: str):
        self._add_history('system', content)
    
    def _add_instruct_history(self, content: str):
        self._add_history(self.sys_role, content, self.sys_template, "<系统>")
    
    def _add_memory_history(self, content: str):
        self._add_history(self.sys_role, content, self.sys_template, "<记忆>")

    def _append_chat_buffer(self, user: str, content: str):
        self.chat_count += 1
        if len(self.chat_buffer) < self.chat_maxsize:
            self.chat_buffer.append({
                'user': user,
                'content': content
            })
        else:
            # 水池采样保证均匀抽取，同时保留时间顺序
            rand = random.randint(0, self.chat_count - 1)
            if rand < len(self.chat_buffer):
                self.chat_buffer.pop(rand)
                self.chat_buffer.append({
                    'user': user,
                    'content': content
                })

    async def run(self):
        if self.config.mcp_support:
            await self.init_mcp()
        while True:
            try:
                task = self.task_queue.get_nowait()
                print(self.state, task)
            except asyncio.QueueEmpty:
                task = None
            
            if isinstance(task, ChatMessage): ## TODO: 支持模型自主选择是否回复
                message = task.get_value(self)
                self._append_chat_buffer(message['user'], message['content'])
            if isinstance(task, MultiChatMessage):
                for msg in task.get_value(self)['messages']:
                    self._append_chat_buffer(msg['user'], msg['content'])
            if isinstance(task, SongInfo):
                self.about_to_sing = True
                self.song_id = task.get_value(self)["song_id"]

            match self.state:
                case LLMState.IDLE:
                    if isinstance(task, ASRActivated):
                        self._switch_to_waiting4asr()
                    elif self.about_to_sing:
                        await self.results_queue.put(
                            ReadyToSing(self, self.song_id)
                        )
                        self._switch_to_singing()
                    elif self.chat_buffer:
                        self._add_multi_chat_history(self.chat_buffer)
                        self.chat_buffer.clear()
                        self.chat_count = 0
                        self._switch_to_generating()
                    elif self.do_start_topic and time.time() - self.idle_start_time > self.idle_timeout:
                        self._add_instruct_history("请随便说点什么吧！")
                        self._switch_to_generating()

                case LLMState.GENERATING:
                    if isinstance(task, ASRActivated):
                        self._switch_to_waiting4asr()
                    if self.generate_task is not None and self.generate_task.done():
                        self._switch_to_waiting4tts()

                case LLMState.WAITING4ASR:
                    if time.time() - self.waiting4asr_start_time > self.asr_timeout:
                        self._switch_to_idle() # ASR超时，回到待机
                    if isinstance(task, ASRMessage):
                        message_value = task.get_value(self)
                        speaker_name = message_value["speaker_name"]
                        content = message_value["message"]
                        self._add_asr_history(speaker_name, content)
                        self.asr_counter -= 1 # 有人说话完毕，计数器-1
                    if isinstance(task, ASRActivated):
                        self.asr_counter += 1 # 有人开始说话，计数器+1
                    if self.asr_counter <= 0: # 所有人说话完毕，开始生成
                        self._switch_to_generating()

                case LLMState.WAITING4TTS:
                    if time.time() - self.waiting4tts_start_time > self.tts_timeout:
                        self._switch_to_idle() # 太久没有TTS完成信息，说明TTS生成失败，回到待机
                    if isinstance(task, AudioFinished):
                        self._switch_to_idle()
                    elif isinstance(task, ASRActivated):
                        self._switch_to_waiting4asr()
                
                case LLMState.SINGING:
                    if isinstance(task, FinishedSinging):
                        self._switch_to_idle()

            await asyncio.sleep(0.1) # 避免卡死事件循环
    
    async def start_generating(self) -> None:
        iterator = self.iter_sentences_emotions()
        try:
            async for sentence, emotion in iterator:
                self.generated_text += sentence
                await self.results_queue.put(
                    LLMMessage(
                        self,
                        sentence,
                        str(uuid4()),
                        emotion
                    )
                )
        except asyncio.CancelledError:
            await iterator.aclose()
        finally:
            await self.results_queue.put(LLMEOS(self))
    
    @torch.no_grad()
    async def get_emotion(self, text: str) -> dict[str, float]:
        print(text)
        labels = ['neutral', 'like', 'sad', 'disgust', 'anger', 'happy']
        ids = self.classifier_tokenizer([text], return_tensors="pt")['input_ids']
        probs = (
            (await asyncio.to_thread(self.classifier_model, input_ids=ids))
            .logits
            .softmax(dim=-1)
            .squeeze()
        )
        return dict(zip(labels, probs.tolist()))
    
    def dict2message(self, message: dict[str, Any]):
        from openai.types.chat import (
            ChatCompletionUserMessageParam,
            ChatCompletionAssistantMessageParam,
            ChatCompletionSystemMessageParam,
            ChatCompletionToolMessageParam
        )
        
        match message:
            case {'role': 'user', 'content': content}:
                return ChatCompletionUserMessageParam(role="user", content=str(content))
            case {'role': 'assistant', 'content': content, **rest}:
                return ChatCompletionAssistantMessageParam(
                    role="assistant", 
                    content=str(content),
                    tool_calls=rest.get('tool_calls') or []
                )
            case {'role': 'system', 'content': content}:
                return ChatCompletionSystemMessageParam(role="system", content=str(content))
            case {'role': 'tool', 'content': content, 'tool_call_id': tool_call_id}:
                return ChatCompletionToolMessageParam(
                    role="tool", 
                    content=str(content),
                    tool_call_id=str(tool_call_id)
                )
            case _:
                raise ValueError(f"Invalid message: {message}")

    def get_mcp_tools(self):
        ## By: Claude Code (Powered by Kimi-K2)
        """获取所有可用的MCP工具"""
        if not self.config.mcp_support:
            return []
        
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema
                }
            }
            for tool_list in self.tools
            for tool in tool_list
        ]

    async def execute_mcp_tool(self, tool_name: str, arguments):
        ## By: Claude Code (Powered by Kimi-K2)
        """执行指定的MCP工具调用"""
        if not self.config.mcp_support:
            raise ValueError("MCP support is not enabled")
        
        # 查找对应的工具会话
        for session_idx, tool_list in enumerate(self.tools):
            for tool in tool_list:
                if tool.name == tool_name:
                    session = self.mcp_sessions[session_idx]
                    try:
                        result = await session.call_tool(tool_name, arguments)
                        # 将 CallToolResult 转为可序列化的字典格式
                        if hasattr(result, 'content'):
                            # 处理 CallToolResult 对象
                            content_list = []
                            for content_item in result.content:
                                if hasattr(content_item, 'text'):
                                    content_list.append({"type": "text", "text": content_item.text})
                                elif hasattr(content_item, 'type') and hasattr(content_item, 'data'):
                                    content_list.append({"type": content_item.type, "data": content_item.data})
                            return {"content": content_list}
                        else:
                            # 处理其他格式的结果
                            return {"content": [{"type": "text", "text": str(result)}]}
                    except Exception as e:
                        print(f"Error executing MCP tool {tool_name}: {e}")
                        return {"error": str(e)}
        
        raise ValueError(f"Tool {tool_name} not found")
    
    async def _generate_with_tools_stream(self, messages, available_tools):
        print(messages)
        ## By: Claude Code (Powered by Kimi-K2)
        """流式模式：使用工具进行对话生成的辅助方法"""
        try:
            request_params = {
                "model": self.model_id,
                "messages": messages,
                "stream": True,
                "temperature": self.temperature
            }
            
            if available_tools:
                request_params["tools"] = available_tools
                request_params["tool_choice"] = "auto"
            
            response_stream = await self.client.chat.completions.create(**request_params)
            tool_calls_accumulator = {}
            
            async for chunk in response_stream:
                if chunk.choices and (delta := chunk.choices[0].delta):
                    content = delta.content or ""
                    tool_calls_output = []
                    
                    if delta.tool_calls:
                        for tool_call_delta in delta.tool_calls:
                            index = tool_call_delta.index
                            if index not in tool_calls_accumulator:
                                tool_calls_accumulator[index] = {
                                    "id": "",
                                    "type": "function",
                                    "function": {
                                        "name": "",
                                        "arguments": ""
                                    }
                                }
                            
                            # 累积工具调用信息
                            if tool_call_delta.id:
                                tool_calls_accumulator[index]["id"] = tool_call_delta.id
                            if tool_call_delta.function and tool_call_delta.function.name:
                                tool_calls_accumulator[index]["function"]["name"] = tool_call_delta.function.name
                            if tool_call_delta.function and tool_call_delta.function.arguments:
                                tool_calls_accumulator[index]["function"]["arguments"] += tool_call_delta.function.arguments
                    
                    # 只有在流结束时才输出完整的工具调用
                    finish_reason = chunk.choices[0].finish_reason
                    if finish_reason == "tool_calls":
                        tool_calls_output = list(tool_calls_accumulator.values())
                    
                    yield {
                        "content": content,
                        "tool_calls": tool_calls_output,
                        "finish_reason": finish_reason
                    }
        except Exception as e:
            print(f"Error in _generate_with_tools_stream: {e}")
            yield {
                "content": f"Some one tell the developers that there's something wrong with my AI: {e}",
                "tool_calls": [],
                "finish_reason": "stop"
            }

    async def iter_sentences_emotions(self):
        ## By: KyvYang + Claude Code (Powered by Kimi-K2)
        generating_sentence = ""
        try:
            # 获取可用的MCP工具
            available_tools = self.get_mcp_tools()
            
            # 创建消息历史
            current_messages = [self.dict2message(message) for message in self.history]
            
            # 循环处理工具调用，直到没有更多工具调用
            while True:
                # 使用流式API生成响应
                accumulated_content = ""
                tool_calls_buffer = []
                
                async for chunk in self._generate_with_tools_stream(current_messages, available_tools):
                    content = chunk["content"] or ""
                    tool_calls = chunk["tool_calls"]
                    finish_reason = chunk["finish_reason"]
                    
                    # 累积内容
                    accumulated_content += str(content)
                    
                    # 处理内容流
                    if content and not tool_calls_buffer:  # 没有待处理的工具调用
                        generating_sentence += str(content)
                        
                        # 检查是否有完整的句子可以发送
                        sentences = split_text(generating_sentence)
                        if sentences[:-1]:
                            for sentence in sentences[:-1]:
                                if sentence.strip():
                                    yield sentence.strip(), await self.get_emotion(sentence.strip())
                            generating_sentence = sentences[-1]
                    
                    # 收集工具调用信息（在流结束时处理）
                    if tool_calls:
                        tool_calls_buffer.extend(tool_calls)
                    
                    # 流结束处理
                    if finish_reason == "stop" or finish_reason == "tool_calls":
                        break
                
                # 处理工具调用（如果有）
                if tool_calls_buffer and self.config.mcp_support:
                    import json
                    
                    # 添加助手消息（包含工具调用请求）
                    if accumulated_content.strip() or tool_calls_buffer:
                        from openai.types.chat import ChatCompletionAssistantMessageParam
                        
                        tool_calls = []
                        for tool_call in tool_calls_buffer:
                            tool_calls.append({
                                "id": tool_call["id"],
                                "type": "function",
                                "function": {
                                    "name": tool_call["function"]["name"],
                                    "arguments": tool_call["function"]["arguments"]
                                }
                            })
                        
                        assistant_message = ChatCompletionAssistantMessageParam(
                            role="assistant",
                            content=accumulated_content,
                            tool_calls=tool_calls
                        )
                        current_messages.append(assistant_message)
                    
                    # 执行所有工具调用
                    for tool_call in tool_calls_buffer:
                        tool_name = tool_call["function"]["name"]
                        try:
                            tool_args = json.loads(tool_call["function"]["arguments"] or "{}")
                            result = await self.execute_mcp_tool(tool_name, tool_args)
                            
                            # 添加工具结果到消息历史
                            from openai.types.chat import ChatCompletionToolMessageParam
                            
                            # 确保结果是可序列化的格式
                            tool_content = json.dumps(result)
                            
                            tool_result_message = ChatCompletionToolMessageParam(
                                role="tool",
                                content=tool_content,
                                tool_call_id=tool_call["id"]
                            )
                            current_messages.append(tool_result_message)
                            
                            # 输出简洁的调用提示给用户
                            tool_hint = f"<调用了 {tool_name} 工具成功>"
                            generating_sentence += tool_hint
                            
                        except Exception as e:
                            error_hint = f"<调用 {tool_name} 工具失败：{e}>"
                            generating_sentence += error_hint
                    
                    # 继续下一轮循环，让LLM基于工具结果继续生成
                    continue
                
                # 没有工具调用，结束循环
                break

        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(repr(e))
            yield f"Someone tell the developer that there's something wrong with my AI: {repr(e)}", {
                "neutral": 1.0,
                "like": 0.0,
                "sad": 0.0,
                "disgust": 0.0,
                "anger": 0.0,
                "happy": 0.0
            }
        
        # 处理剩余的句子
        if generating_sentence.strip():
            yield generating_sentence.strip(), await self.get_emotion(generating_sentence)

__all__ = ["LLM"]
