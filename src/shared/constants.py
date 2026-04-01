# SwarmClone Backend - 共享常量定义

"""
本模块包含系统范围内共享的常量
"""


# 系统常量
SYSTEM_NAME = "SwarmClone"
SYSTEM_VERSION = "0.4.0"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 4927


# 事件名称常量
class Events:
    """系统事件名称常量"""
    
    # 系统事件
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_ERROR = "system.error"
    
    # 模块事件
    MODULE_LOADED = "module.loaded"
    MODULE_UNLOADED = "module.unloaded"
    MODULE_ERROR = "module.error"
    
    # 直播事件
    STREAM_STARTED = "stream.started"
    STREAM_STOPPED = "stream.stopped"
    STREAM_STATUS_CHANGED = "stream.status_changed"
    
    # 弹幕事件
    DANMAKU_RECEIVED = "danmaku.received"
    DANMAKU_PROCESSED = "danmaku.processed"
    DANMAKU_IGNORED = "danmaku.ignored"
    
    # 礼物事件
    GIFT_RECEIVED = "gift.received"
    GIFT_PROCESSED = "gift.processed"
    
    # 关注事件
    FOLLOW_RECEIVED = "follow.received"
    FOLLOW_PROCESSED = "follow.processed"
    
    # AI 对话事件
    CONVERSATION_REQUEST = "conversation.request"
    CONVERSATION_RESPONSE = "conversation.response"
    CONVERSATION_ERROR = "conversation.error"
    
    # 语音合成事件
    TTS_GENERATE = "tts.generate"
    TTS_COMPLETED = "tts.completed"
    TTS_ERROR = "tts.error"
    
    # 动作控制事件
    MOTION_COMMAND = "motion.command"
    MOTION_COMPLETED = "motion.completed"
    MOTION_ERROR = "motion.error"
    
    # 模型事件
    MODEL_REQUEST = "model.request"
    MODEL_RESPONSE = "model.response"
    MODEL_ERROR = "model.error"


# 配置键常量
class ConfigKeys:
    """常用配置键常量"""
    
    # 系统配置
    HOST = "host"
    PORT = "port"
    LOG_LEVEL = "log_level"
    
    # API 配置
    API_TIMEOUT = "api_timeout"
    API_RETRY_COUNT = "api_retry_count"
    
    # AI 模型配置
    MODEL_PROVIDER = "model_provider"
    MODEL_NAME = "model_name"
    API_KEY = "api_key"
    BASE_URL = "base_url"
    MAX_TOKENS = "max_tokens"
    TEMPERATURE = "temperature"
    
    # TTS 配置
    TTS_PROVIDER = "tts_provider"
    TTS_VOICE = "tts_voice"
    TTS_SPEED = "tts_speed"
    
    # 直播平台配置
    LIVE_PLATFORM = "live_platform"
    ROOM_ID = "room_id"
    COOKIE = "cookie"
    
    # 动作配置
    EXPRESSION_ENABLED = "expression_enabled"
    GESTURE_ENABLED = "gesture_enabled"
    LIP_SYNC_ENABLED = "lip_sync_enabled"


# 错误码常量
class ErrorCodes:
    """系统错误码"""
    
    SUCCESS = 0
    
    # 通用错误 (1-999)
    GENERAL_ERROR = 1
    INVALID_PARAMETER = 2
    TIMEOUT = 3
    NOT_FOUND = 4
    PERMISSION_DENIED = 5
    
    # 模块错误 (1000-1999)
    MODULE_NOT_FOUND = 1001
    MODULE_LOAD_FAILED = 1002
    MODULE_INIT_FAILED = 1003
    MODULE_START_FAILED = 1004
    
    # API 错误 (2000-2999)
    API_ERROR = 2001
    API_RATE_LIMIT = 2002
    API_AUTH_FAILED = 2003
    
    # 直播错误 (3000-3999)
    LIVE_CONNECT_FAILED = 3001
    LIVE_DISCONNECTED = 3002
    LIVE_INVALID_ROOM = 3003
    
    # AI 模型错误 (4000-4999)
    MODEL_ERROR = 4001
    MODEL_TIMEOUT = 4002
    MODEL_INVALID_RESPONSE = 4003
    
    # TTS 错误 (5000-5999)
    TTS_ERROR = 5001
    TTS_TIMEOUT = 5002
    TTS_INVALID_AUDIO = 5003
    
    # 动作控制错误 (6000-6999)
    MOTION_ERROR = 6001
    MOTION_TIMEOUT = 6002


# 平台常量
class Platforms:
    """支持的平台常量"""
    BILIBILI = "bilibili"
    TWITCH = "twitch"
    YOUTUBE = "youtube"
    DOUYIN = "douyin"
    HUYA = "huya"
    DOUYU = "douyu"


# 情感类型常量
class Emotions:
    """情感类型常量"""
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    SURPRISED = "surprised"
    EXCITED = "excited"
    CALM = "calm"
    PLAYFUL = "playful"


# 默认值常量
class Defaults:
    """默认值常量"""
    
    # 超时时间（秒）
    API_TIMEOUT = 30.0
    EVENT_TIMEOUT = 10.0
    CONNECTION_TIMEOUT = 5.0
    
    # 重试次数
    MAX_RETRY_COUNT = 3
    RETRY_DELAY = 1.0
    
    # AI 模型参数
    DEFAULT_TEMPERATURE = 0.7
    DEFAULT_MAX_TOKENS = 500
    
    # TTS 参数
    DEFAULT_TTS_SPEED = 1.0
    DEFAULT_TTS_PITCH = 1.0
    DEFAULT_TTS_VOLUME = 1.0
    
    # 日志
    DEFAULT_LOG_LEVEL = "INFO"
    
    # 间隔时间（秒）
    STATUS_CHECK_INTERVAL = 30.0
    HEARTBEAT_INTERVAL = 60.0


# 文件路径常量
class Paths:
    """文件路径常量"""
    CONFIG_FILE = "config.toml"
    MODULE_CONFIG_FILE = "config.json"
    LOG_DIR = "logs"
    MODULES_DIR = "src/modules"
    TEMPLATE_DIR = "template"
