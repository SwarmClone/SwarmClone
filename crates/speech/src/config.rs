use std::fs;
use std::path::PathBuf;

use serde::{Deserialize, Serialize};

use crate::error::{Result, SpeechError};

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct SpeechConfig {
    pub dashscope: DashScopeConfig,
    pub tts: TtsConfig,
    pub asr: AsrConfig,
    #[serde(default)]
    pub vad: VadConfig,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct DashScopeConfig {
    pub websocket_url: String,
    pub api_key: String,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct TtsConfig {
    pub model: String,
    pub voice: String,
    #[serde(default = "default_tts_format")]
    pub format: String,
    #[serde(default = "default_sample_rate")]
    pub sample_rate: u32,
    #[serde(default = "default_volume")]
    pub volume: u32,
    #[serde(default = "default_rate")]
    pub rate: f32,
    #[serde(default = "default_pitch")]
    pub pitch: f32,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct AsrConfig {
    pub model: String,
    #[serde(default = "default_asr_format")]
    pub format: String,
    #[serde(default = "default_sample_rate")]
    pub sample_rate: u32,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct VadConfig {
    #[serde(default = "default_threshold")]
    pub rms_threshold: f32,
    #[serde(default = "default_start_frames")]
    pub start_frames: usize,
    #[serde(default = "default_end_silence_ms")]
    pub end_silence_ms: u64,
    #[serde(default = "default_frame_ms")]
    pub frame_ms: u64,
}

impl Default for VadConfig {
    fn default() -> Self {
        Self {
            rms_threshold: default_threshold(),
            start_frames: default_start_frames(),
            end_silence_ms: default_end_silence_ms(),
            frame_ms: default_frame_ms(),
        }
    }
}

impl SpeechConfig {
    pub fn from_config_file() -> Result<Self> {
        let path = config_path();
        let content = fs::read_to_string(&path)
            .map_err(|e| SpeechError::Config(format!("读取 {:?} 失败: {}", path, e)))?;
        let root: toml::Value = toml::from_str(&content)
            .map_err(|e| SpeechError::Config(format!("解析 {:?} 失败: {}", path, e)))?;
        let speech = root
            .get("speech")
            .cloned()
            .ok_or_else(|| SpeechError::Config("缺少 [speech] 配置".to_string()))?;
        speech
            .try_into()
            .map_err(|e| SpeechError::Config(format!("解析 [speech] 失败: {}", e)))
    }
}

pub fn config_path() -> PathBuf {
    std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|p| p.to_path_buf()))
        .unwrap_or_else(|| PathBuf::from("."))
        .join("config.toml")
}

fn default_tts_format() -> String {
    "mp3".to_string()
}
fn default_asr_format() -> String {
    "pcm".to_string()
}
fn default_sample_rate() -> u32 {
    16_000
}
fn default_volume() -> u32 {
    50
}
fn default_rate() -> f32 {
    1.0
}
fn default_pitch() -> f32 {
    1.0
}
fn default_threshold() -> f32 {
    0.015
}
fn default_start_frames() -> usize {
    3
}
fn default_end_silence_ms() -> u64 {
    800
}
fn default_frame_ms() -> u64 {
    20
}
