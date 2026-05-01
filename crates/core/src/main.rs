use std::net::SocketAddr;

use axum::extract::State;
use axum::extract::ws::{Message as WsMessage, WebSocket, WebSocketUpgrade};
use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Json, Router};
use base64::Engine;
use futures_util::{SinkExt, StreamExt};
use llm::session::Session;
use serde::{Deserialize, Serialize};
use speech::asr::{self, AsrEvent};
use speech::config::SpeechConfig;
use speech::tts::{self, TtsEvent};
use speech::vad::{EnergyVad, VadEvent};
use tower_http::cors::CorsLayer;
use utils::log;

#[derive(Clone)]
struct AppState {
    speech: Option<SpeechConfig>,
}

#[derive(Debug, Serialize)]
struct HealthResponse {
    status: &'static str,
    speech_configured: bool,
}

#[derive(Debug, Serialize)]
struct PublicConfigResponse {
    roles: Vec<String>,
    providers: Vec<String>,
    speech_configured: bool,
}

#[derive(Debug, Deserialize)]
struct ChatRequest {
    text: String,
    #[serde(default = "default_role")]
    role: String,
}

#[derive(Debug, Serialize)]
struct ChatResponse {
    text: String,
}

#[derive(Debug, Deserialize)]
struct TtsRequest {
    text: String,
}

#[derive(Debug, Serialize)]
struct TtsResponse {
    audio_base64: String,
    mime_type: String,
}

#[derive(Debug, Serialize)]
#[serde(tag = "type")]
enum RealtimeEvent {
    #[serde(rename = "status")]
    Status { stage: String, message: String },
    #[serde(rename = "vad.started")]
    VadStarted,
    #[serde(rename = "vad.ended")]
    VadEnded,
    #[serde(rename = "asr.partial")]
    AsrPartial { text: String },
    #[serde(rename = "asr.final")]
    AsrFinal { text: String },
    #[serde(rename = "llm.completed")]
    LlmCompleted { text: String },
    #[serde(rename = "tts.started")]
    TtsStarted { task_id: String },
    #[serde(rename = "tts.chunk")]
    TtsChunk { audio_base64: String },
    #[serde(rename = "tts.completed")]
    TtsCompleted,
    #[serde(rename = "error")]
    Error { message: String },
}

#[derive(Debug)]
struct ApiError(String);

impl std::fmt::Display for ApiError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        (StatusCode::INTERNAL_SERVER_ERROR, self.0).into_response()
    }
}

#[tokio::main]
async fn main() {
    log::set_log_level(log::LogLevel::Debug);

    let args = std::env::args().collect::<Vec<_>>();
    if args.get(1).map(|s| s.as_str()) == Some("smoke") {
        let input = args
            .get(2)
            .cloned()
            .unwrap_or_else(|| "你好，请做一个简短的自我介绍。".to_string());
        if let Err(e) = smoke_test(&input).await {
            log::error!("smoke", "{}", e);
            std::process::exit(1);
        }
        return;
    }

    if let Err(e) = serve().await {
        log::error!("backend", "{}", e);
        std::process::exit(1);
    }
}

async fn serve() -> Result<(), ApiError> {
    let speech = match SpeechConfig::from_config_file() {
        Ok(config) => Some(config),
        Err(e) => {
            log::error!("config", "语音配置未就绪: {}", e);
            None
        }
    };
    let state = AppState { speech };
    let app = Router::new()
        .route("/health", get(health))
        .route("/api/config/public", get(public_config))
        .route("/api/roles", get(roles))
        .route("/api/chat", post(chat))
        .route("/api/tts", post(tts_once))
        .route("/api/realtime", get(realtime))
        .layer(CorsLayer::permissive())
        .with_state(state);

    let addr = SocketAddr::from(([127, 0, 0, 1], 17860));
    log::info!("backend", "监听 http://{}", addr);
    let listener = tokio::net::TcpListener::bind(addr)
        .await
        .map_err(|e| ApiError(e.to_string()))?;
    axum::serve(listener, app)
        .await
        .map_err(|e| ApiError(e.to_string()))
}

async fn health(State(state): State<AppState>) -> Json<HealthResponse> {
    Json(HealthResponse {
        status: "ok",
        speech_configured: state.speech.is_some(),
    })
}

async fn public_config(State(state): State<AppState>) -> Json<PublicConfigResponse> {
    Json(PublicConfigResponse {
        roles: llm::session::available_roles(),
        providers: llm::session::available_providers(),
        speech_configured: state.speech.is_some(),
    })
}

async fn roles() -> Json<Vec<String>> {
    Json(llm::session::available_roles())
}

async fn chat(Json(req): Json<ChatRequest>) -> Result<Json<ChatResponse>, ApiError> {
    let text = run_llm(&req.role, &req.text).await?;
    Ok(Json(ChatResponse { text }))
}

async fn tts_once(
    State(state): State<AppState>,
    Json(req): Json<TtsRequest>,
) -> Result<Json<TtsResponse>, ApiError> {
    let config = state
        .speech
        .ok_or_else(|| ApiError("缺少 speech 配置".to_string()))?;
    let mut rx = tts::synthesize_stream(config, req.text)
        .await
        .map_err(|e| ApiError(e.to_string()))?;
    let mut audio = Vec::new();

    while let Some(event) = rx.recv().await {
        match event.map_err(|e| ApiError(e.to_string()))? {
            TtsEvent::Audio(bytes) => audio.extend(bytes),
            TtsEvent::Failed { code, message } => {
                return Err(ApiError(format!("TTS 失败 {:?}: {}", code, message)));
            }
            TtsEvent::Finished { .. } => break,
            _ => {}
        }
    }

    Ok(Json(TtsResponse {
        audio_base64: base64::engine::general_purpose::STANDARD.encode(audio),
        mime_type: "audio/mpeg".to_string(),
    }))
}

async fn realtime(State(state): State<AppState>, ws: WebSocketUpgrade) -> Response {
    ws.on_upgrade(move |socket| handle_realtime(socket, state))
}

async fn handle_realtime(socket: WebSocket, state: AppState) {
    let Some(config) = state.speech else {
        let (mut tx, _) = socket.split();
        let _ = send_event(
            &mut tx,
            &RealtimeEvent::Error {
                message: "缺少 speech 配置".to_string(),
            },
        )
        .await;
        return;
    };

    let (mut tx, mut rx) = socket.split();
    let mut vad = EnergyVad::new(config.vad.clone());
    let mut utterance = Vec::<u8>::new();

    let _ = send_event(
        &mut tx,
        &RealtimeEvent::Status {
            stage: "ready".to_string(),
            message: "后端实时链路已连接".to_string(),
        },
    )
    .await;

    while let Some(message) = rx.next().await {
        match message {
            Ok(WsMessage::Binary(frame)) => {
                let event = vad.accept_pcm16(&frame);
                match event {
                    Some(VadEvent::SpeechStarted) => {
                        utterance.clear();
                        utterance.extend(frame);
                        let _ = send_event(&mut tx, &RealtimeEvent::VadStarted).await;
                    }
                    Some(VadEvent::SpeechEnded) => {
                        let _ = process_utterance(&mut tx, config.clone(), utterance.clone()).await;
                        utterance.clear();
                    }
                    None if vad.is_speaking() => utterance.extend(frame),
                    None => {}
                }
            }
            Ok(WsMessage::Text(text)) if text == "flush" => {
                if !utterance.is_empty() {
                    let _ = process_utterance(&mut tx, config.clone(), utterance.clone()).await;
                    utterance.clear();
                }
            }
            Ok(WsMessage::Close(_)) => return,
            Err(e) => {
                let _ = send_event(
                    &mut tx,
                    &RealtimeEvent::Error {
                        message: e.to_string(),
                    },
                )
                .await;
                return;
            }
            _ => {}
        }
    }
}

async fn process_utterance<S>(
    tx: &mut S,
    config: SpeechConfig,
    audio: Vec<u8>,
) -> Result<(), ApiError>
where
    S: SinkExt<WsMessage> + Unpin,
    <S as futures_util::Sink<WsMessage>>::Error: std::fmt::Display,
{
    send_event(tx, &RealtimeEvent::VadEnded).await?;
    send_event(
        tx,
        &RealtimeEvent::Status {
            stage: "asr".to_string(),
            message: "开始识别语音".to_string(),
        },
    )
    .await?;
    let mut asr_rx = asr::recognize_stream(config.clone(), audio)
        .await
        .map_err(|e| ApiError(e.to_string()))?;
    let mut user_text = String::new();
    while let Some(event) = asr_rx.recv().await {
        match event.map_err(|e| ApiError(e.to_string()))? {
            AsrEvent::Partial { text } => {
                send_event(tx, &RealtimeEvent::AsrPartial { text }).await?
            }
            AsrEvent::Final { text } => {
                user_text = text.clone();
                send_event(tx, &RealtimeEvent::AsrFinal { text }).await?;
            }
            AsrEvent::Failed { code, message } => {
                return Err(ApiError(format!("ASR 失败 {:?}: {}", code, message)));
            }
            _ => {}
        }
    }

    if user_text.trim().is_empty() {
        return Err(ApiError("ASR 未返回有效文本".to_string()));
    }

    send_event(
        tx,
        &RealtimeEvent::Status {
            stage: "llm".to_string(),
            message: "开始生成回复".to_string(),
        },
    )
    .await?;
    let answer = run_llm("default", &user_text).await?;
    send_event(
        tx,
        &RealtimeEvent::LlmCompleted {
            text: answer.clone(),
        },
    )
    .await?;

    send_event(
        tx,
        &RealtimeEvent::Status {
            stage: "tts".to_string(),
            message: "开始语音合成".to_string(),
        },
    )
    .await?;
    let mut tts_rx = tts::synthesize_stream(config, answer)
        .await
        .map_err(|e| ApiError(e.to_string()))?;
    while let Some(event) = tts_rx.recv().await {
        match event.map_err(|e| ApiError(e.to_string()))? {
            TtsEvent::Started { task_id } => {
                send_event(tx, &RealtimeEvent::TtsStarted { task_id }).await?
            }
            TtsEvent::Audio(bytes) => {
                send_event(
                    tx,
                    &RealtimeEvent::TtsChunk {
                        audio_base64: base64::engine::general_purpose::STANDARD.encode(bytes),
                    },
                )
                .await?;
            }
            TtsEvent::Finished { .. } => {
                send_event(tx, &RealtimeEvent::TtsCompleted).await?;
                break;
            }
            TtsEvent::Failed { code, message } => {
                return Err(ApiError(format!("TTS 失败 {:?}: {}", code, message)));
            }
        }
    }
    Ok(())
}

async fn send_event<S>(tx: &mut S, event: &RealtimeEvent) -> Result<(), ApiError>
where
    S: SinkExt<WsMessage> + Unpin,
    <S as futures_util::Sink<WsMessage>>::Error: std::fmt::Display,
{
    let text = serde_json::to_string(event).map_err(|e| ApiError(e.to_string()))?;
    tx.send(WsMessage::Text(text))
        .await
        .map_err(|e| ApiError(e.to_string()))
}

async fn run_llm(role: &str, text: &str) -> Result<String, ApiError> {
    let mut session = Session::new(role).map_err(|e| ApiError(e.to_string()))?;
    session
        .chat(text)
        .await
        .map_err(|e| ApiError(e.to_string()))
}

async fn smoke_test(input: &str) -> Result<(), ApiError> {
    let speech = SpeechConfig::from_config_file().map_err(|e| ApiError(e.to_string()))?;
    let answer = run_llm("default", input).await?;
    log::info!("smoke", "LLM 回复: {}", answer);
    let mut rx = tts::synthesize_stream(speech, answer)
        .await
        .map_err(|e| ApiError(e.to_string()))?;
    let mut audio = Vec::new();
    while let Some(event) = rx.recv().await {
        match event.map_err(|e| ApiError(e.to_string()))? {
            TtsEvent::Audio(bytes) => audio.extend(bytes),
            TtsEvent::Failed { code, message } => {
                return Err(ApiError(format!("TTS 失败 {:?}: {}", code, message)));
            }
            TtsEvent::Finished { .. } => break,
            _ => {}
        }
    }
    tokio::fs::write("smoke-output.mp3", audio)
        .await
        .map_err(|e| ApiError(e.to_string()))?;
    log::info!("smoke", "已写入 smoke-output.mp3");
    Ok(())
}

fn default_role() -> String {
    "default".to_string()
}
