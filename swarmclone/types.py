from __future__ import annotations

from typing import Any, TypedDict
from collections.abc import Sequence

# Emotion Type - 情感分析结果类型
Emotion = TypedDict("Emotion", {
    "neutral": float,
    "like": float,
    "sad": float,
    "disgust": float,
    "anger": float,
    "happy": float
})

# Alignment Data Type - 先用到的基础类型
AlignedToken = TypedDict("AlignedToken", {"token": str, "duration": float})
AlignedSequence = Sequence[AlignedToken]

# Module Manager Types
ConfigInfo = TypedDict("ConfigInfo", {"module_name": str, "desc": str, "config": list[dict[str, Any]]})

# Message Types
SignalContent = TypedDict("SignalContent", {"name": str})
ASRContent = TypedDict("ASRContent", {"speaker_name": str, "message": str})
LLMContent = TypedDict("LLMContent", {"content": str, "id": str, "emotion": Emotion})
TTSAlignedContent = TypedDict("TTSAlignedContent", {"id": str, "data": bytes, "align_data": AlignedSequence})
ChatContent = TypedDict("ChatContent", {"user": str, "content": str})
MultiChatContent = TypedDict("MultiChatContent", {"messages": list[ChatContent]})
SongInfoContent = TypedDict("SongInfoContent", {"song_id": str, "song_path": str, "vocal_path": str, "subtitle_path": str})
SingSigContent = TypedDict("SingSigContent", {"song_id": str})
ActiveActionContent = TypedDict("ActiveActionContent", {"action_ids": list[str]})
ParametersUpdateContent = TypedDict("ParametersUpdateContent", {"updates": dict[str, float]})
ProviderRequestContent = TypedDict("ProviderRequestContent", {"messages": list[dict[str, str]], "stream": bool})
ProviderResponseContent = TypedDict("ProviderResponseContent", {"content": str})
ProviderResponseStreamContent = TypedDict("ProviderResponseStreamContent", {"delta": str, "end": bool})

