use futures_util::{SinkExt, StreamExt};
use http::Request;
use serde_json::json;
use tokio::sync::mpsc;
use tokio_tungstenite::tungstenite::Message;
use uuid::Uuid;

use crate::config::SpeechConfig;
use crate::error::{Result, SpeechError};

#[derive(Debug)]
pub enum TtsEvent {
    Started {
        task_id: String,
    },
    Audio(Vec<u8>),
    Finished {
        task_id: String,
        characters: Option<u64>,
    },
    Failed {
        code: Option<String>,
        message: String,
    },
}

pub async fn synthesize_stream(
    config: SpeechConfig,
    text: String,
) -> Result<mpsc::Receiver<Result<TtsEvent>>> {
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
                "task": "tts",
                "function": "SpeechSynthesizer",
                "model": config.tts.model,
                "parameters": {
                    "text_type": "PlainText",
                    "voice": config.tts.voice,
                    "format": config.tts.format,
                    "sample_rate": config.tts.sample_rate,
                    "volume": config.tts.volume,
                    "rate": config.tts.rate,
                    "pitch": config.tts.pitch
                },
                "input": {}
            }
        });

        if let Err(e) = write.send(Message::Text(run_task.to_string())).await {
            let _ = tx.send(Err(e.into())).await;
            return;
        }

        let mut started = false;
        while let Some(message) = read.next().await {
            let message = match message {
                Ok(m) => m,
                Err(e) => {
                    let _ = tx.send(Err(e.into())).await;
                    return;
                }
            };

            match message {
                Message::Text(raw) => {
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
                            started = true;
                            let id = value
                                .pointer("/header/task_id")
                                .and_then(|v| v.as_str())
                                .unwrap_or_default()
                                .to_string();
                            let _ = tx.send(Ok(TtsEvent::Started { task_id: id })).await;

                            let continue_task = json!({
                                "header": {
                                    "action": "continue-task",
                                    "task_id": task_id,
                                    "streaming": "duplex"
                                },
                                "payload": { "input": { "text": text } }
                            });
                            let finish_task = json!({
                                "header": {
                                    "action": "finish-task",
                                    "task_id": task_id,
                                    "streaming": "duplex"
                                },
                                "payload": { "input": {} }
                            });
                            if let Err(e) =
                                write.send(Message::Text(continue_task.to_string())).await
                            {
                                let _ = tx.send(Err(e.into())).await;
                                return;
                            }
                            if let Err(e) = write.send(Message::Text(finish_task.to_string())).await
                            {
                                let _ = tx.send(Err(e.into())).await;
                                return;
                            }
                        }
                        Some("task-finished") => {
                            let id = value
                                .pointer("/header/task_id")
                                .and_then(|v| v.as_str())
                                .unwrap_or_default()
                                .to_string();
                            let characters = value
                                .pointer("/payload/usage/characters")
                                .and_then(|v| v.as_u64());
                            let _ = tx
                                .send(Ok(TtsEvent::Finished {
                                    task_id: id,
                                    characters,
                                }))
                                .await;
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
                                .unwrap_or("TTS task failed")
                                .to_string();
                            let _ = tx.send(Ok(TtsEvent::Failed { code, message })).await;
                            return;
                        }
                        _ => {}
                    }
                }
                Message::Binary(bytes) => {
                    if started {
                        let _ = tx.send(Ok(TtsEvent::Audio(bytes))).await;
                    }
                }
                Message::Close(_) => return,
                _ => {}
            }
        }
    });

    Ok(rx)
}
