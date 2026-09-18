// src-tauri/src/models/config.rs
//! AppConfig mirrors the Python Config dataclass exactly.
//! The JSON schema is identical so existing user configs load without migration.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct AppConfig {
    pub version: u32,

    // Engine
    pub engine_mode: String,
    pub model_size: String,
    pub language: String,
    pub compute_type: String,
    pub local_device: String,
    pub cloud_region: String,
    pub sarvam_model: String,
    pub sarvam_language: String,
    pub enable_sarvam_websocket: bool,
    pub gemini_stt_model: String,
    pub gemini_stt_language: String,

    // Audio
    pub mic_device_index: i32,
    pub sample_rate: u32,
    pub vad_aggressiveness: u8,
    pub silence_timeout_ms: u32,
    pub max_record_seconds: u32,
    pub enable_max_record_limit: bool,

    // Hotkey
    pub hotkey: String,
    pub hotkey_mode: String,

    // Text injection
    pub inject_method: String,
    pub inject_delay_ms: u32,

    // Post-processing
    pub spoken_punctuation: bool,
    pub auto_capitalise: bool,

    // Floating widget
    pub show_floating_widget: bool,
    pub widget_x: i32,
    pub widget_y: i32,
    pub widget_size: u32,
    pub widget_opacity: f32,
    pub widget_always_on_top: bool,

    // System
    pub start_with_windows: bool,
    pub log_level: String,
    pub check_updates: bool,

    // Cloud provider & fallback
    pub cloud_provider: String,
    pub cloud_fallback_on_error: bool,
    pub cloud_fallback_provider: String,
    pub local_fallback_on_cloud_error: bool,

    // UI
    pub theme: String,

    // Preview overlay
    pub show_preview_window: bool,
    pub preview_hide_after_ms: u32,
    pub preview_opacity: f32,
    pub preview_text_color: String,

    // Update checker
    pub last_update_check: String,
    pub skipped_update_version: String,

    // Text polish
    pub enable_polish: bool,
    pub polish_provider: String,
    pub polish_action: String,
    pub custom_polish_prompt: String,
    pub ollama_url: String,
    pub polish_ollama_model: String,
    pub polish_gemini_model: String,
    pub polish_openrouter_model: String,
    pub polish_groq_model: String,

    // Real-time transcription
    pub enable_realtime: bool,
    pub realtime_frequency_ms: u32,

    // App launcher
    pub app_launcher_commands: HashMap<String, String>,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            version: 2,
            engine_mode: "hybrid".into(),
            model_size: "small".into(),
            language: "en".into(),
            compute_type: "int8".into(),
            local_device: "cuda".into(),
            cloud_region: "eastus".into(),
            sarvam_model: "saarika:v2.5".into(),
            sarvam_language: "hi-IN".into(),
            enable_sarvam_websocket: true,
            gemini_stt_model: "gemini-flash-lite-latest".into(),
            gemini_stt_language: "en".into(),
            mic_device_index: -1,
            sample_rate: 16000,
            vad_aggressiveness: 1,
            silence_timeout_ms: 2500,
            max_record_seconds: 30,
            enable_max_record_limit: true,
            hotkey: "ctrl+alt+d".into(),
            hotkey_mode: "toggle".into(),
            inject_method: "clipboard".into(),
            inject_delay_ms: 50,
            spoken_punctuation: true,
            auto_capitalise: true,
            show_floating_widget: true,
            widget_x: 100,
            widget_y: 100,
            widget_size: 64,
            widget_opacity: 0.85,
            widget_always_on_top: true,
            start_with_windows: false,
            log_level: "INFO".into(),
            check_updates: true,
            cloud_provider: "azure".into(),
            cloud_fallback_on_error: true,
            cloud_fallback_provider: "azure".into(),
            local_fallback_on_cloud_error: true,
            theme: "system".into(),
            show_preview_window: true,
            preview_hide_after_ms: 8000,
            preview_opacity: 0.85,
            preview_text_color: "#ffffff".into(),
            last_update_check: String::new(),
            skipped_update_version: String::new(),
            enable_polish: false,
            polish_provider: "ollama".into(),
            polish_action: "Fix Grammar & Spelling".into(),
            custom_polish_prompt: "Rewrite this text to be more concise.".into(),
            ollama_url: "http://localhost:11434".into(),
            polish_ollama_model: "llama3".into(),
            polish_gemini_model: "gemini-flash-lite-latest".into(),
            polish_openrouter_model: String::new(),
            polish_groq_model: String::new(),
            enable_realtime: false,
            realtime_frequency_ms: 800,
            app_launcher_commands: HashMap::new(),
        }
    }
}
