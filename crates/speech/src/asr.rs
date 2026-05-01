use futures_util::{SinkExt, StreamExt};
use http::Request;
use serde_json::json;
use tokio::sync::mpsc;
use tokio_tungstenite::tungstenite::Message;
use uuid::Uuid;

use crate::config::SpeechConfig;
use crate::error::{Result, SpeechError};

#[derive(Debug)]
pub enum AsrEvent {
    Started {
        task_id: String,
    },
    Partial {
        text: String,
    },
    Final {
        text: String,
    },
    Finished {
        task_id: String,
    },
    Failed {
        code: Option<String>,
        message: String,
    },
}

pub async fn recognize_once(config: SpeechConfig, pcm16: Vec<u8>) -> Result<String> {
    let mut rx = recognize_stream(config, pcm16).await?;
    let mut final_text = String::new();

    while let Some(event) = rx.recv().await {
        match event? {
            AsrEvent::Final { text } => final_text = text,
            AsrEvent::Failed { code, message } => {
                return Err(SpeechError::Service(format!(
                    "ASR 失败 {:?}: {}",
                    code, message
                )));
            }
            _ => {}
        }
    }

    Ok(final_text)
}

pub async fn recognize_stream(
    config: SpeechConfig,
    pcm16: Vec<u8>,
) -> Result<mpsc::Receiver<Result<AsrEvent>>> {
    let request = Request::builder()
        .uri(&config.dashscope.websocket_url)
        .header(
            "Authorization",
            format!("Bearer {}", config.dashscope.api_key),
        )
        .header("User-Agent", "SwarmClone/0.1")
        .body(())
        .map_err(|e| SpeechError::Service(e.to_string()))?;

    let (ws, _) = tokio_tungstenite::connect_async(request).await?;
    let (mut write, mut read) = ws.split();
    let (tx, rx) = mpsc::channel(128);
    let task_id = Uuid::new_v4().to_string();

    tokio::spawn(async move {
        let run_task = json!({
            "header": {
                "action": "run-task",
                "task_id": task_id,
                "streaming": "duplex"
            },
            "payload": {
                "task_group": "audio",
                "task": "asr",
                "function": "SpeechRecognizer",
                "model": config.asr.model,
                "parameters": {
                    "format": config.asr.format,
                    "sample_rate": config.asr.sample_rate
                },
                "input": {}
            }
        });

        if let Err(e) = write.send(Message::Text(run_task.to_string())).await {
            let _ = tx.send(Err(e.into())).await;
            return;
        }

        while let Some(message) = read.next().await {
            let message = match message {
                Ok(m) => m,
                Err(e) => {
                    let _ = tx.send(Err(e.into())).await;
                    return;
                }
            };

            if let Message::Text(raw) = message {
                let value: serde_json::Value = match serde_json::from_str(&raw) {
                    Ok(v) => v,
                    Err(e) => {
                        let _ = tx.send(Err(e.into())).await;
                        return;
                    }
                };

                let event = value.pointer("/header/event").and_then(|v| v.as_str());
                match event {
                    Some("task-started") => {
                        let id = value
                            .pointer("/header/task_id")
                            .and_then(|v| v.as_str())
                            .unwrap_or_default()
                            .to_string();
                        let _ = tx.send(Ok(AsrEvent::Started { task_id: id })).await;
                        for chunk in pcm16.chunks(3200) {
                            if let Err(e) = write.send(Message::Binary(chunk.to_vec())).await {
                                let _ = tx.send(Err(e.into())).await;
                                return;
                            }
                        }
                        let finish_task = json!({
                            "header": {
                                "action": "finish-task",
                                "task_id": task_id,
                                "streaming": "duplex"
                            },
                            "payload": { "input": {} }
                        });
                        if let Err(e) = write.send(Message::Text(finish_task.to_string())).await {
                            let _ = tx.send(Err(e.into())).await;
                            return;
                        }
                    }
                    Some("result-generated") => {
                        if let Some(text) = extract_text(&value) {
                            let is_final = value.pointer("/payload/output/sentence_end").is_some()
                                || value
                                    .pointer("/payload/output/is_final")
                                    .and_then(|v| v.as_bool())
                                    .unwrap_or(false)
                                || value.pointer("/payload/output/sentence/text").is_some();
                            let event = if is_final {
                                AsrEvent::Final { text }
                            } else {
                                AsrEvent::Partial { text }
                            };
                            let _ = tx.send(Ok(event)).await;
                        }
                    }
                    Some("task-finished") => {
                        let id = value
                            .pointer("/header/task_id")
                            .and_then(|v| v.as_str())
                            .unwrap_or_default()
                            .to_string();
                        let _ = tx.send(Ok(AsrEvent::Finished { task_id: id })).await;
                        return;
                    }
                    Some("task-failed") => {
                        let code = value
                            .pointer("/header/error_code")
                            .and_then(|v| v.as_str())
                            .map(str::to_string);
                        let message = value
                            .pointer("/header/error_message")
                            .and_then(|v| v.as_str())
                            .unwrap_or("ASR task failed")
                            .to_string();
                        let _ = tx.send(Ok(AsrEvent::Failed { code, message })).await;
                        return;
                    }
                    _ => {}
                }
            }
        }
    });

    Ok(rx)
}

fn extract_text(value: &serde_json::Value) -> Option<String> {
    [
        "/payload/output/text",
        "/payload/output/sentence/text",
        "/payload/output/transcription",
        "/payload/output/result/text",
    ]
    .iter()
    .find_map(|path| {
        value
            .pointer(path)
            .and_then(|v| v.as_str())
            .map(str::to_string)
    })
}
