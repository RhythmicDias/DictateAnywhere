// src-tauri/src/commands/hotkey.rs
//! Global hotkey registration commands.
//! The frontend can call these to re-register when the user changes the hotkey
//! in Settings. The default hotkey is registered directly in lib.rs at startup.

use tauri::{command, AppHandle, Emitter};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, ShortcutState};

/// Parse a hotkey string like "ctrl+alt+d" into a Shortcut.
/// Returns Err if the string is invalid.
fn parse_shortcut(hotkey: &str) -> Result<tauri_plugin_global_shortcut::Shortcut, String> {
    hotkey
        .parse()
        .map_err(|_| format!("Invalid hotkey combination: '{hotkey}'"))
}

/// Register a global hotkey. `mode` is "toggle" or "push_to_talk".
/// On success, pressing the hotkey emits `dictation://toggle`, `dictation://start`,
/// or `dictation://stop` events to all windows.
#[command]
pub fn register_hotkey(app: AppHandle, hotkey: String, mode: String) -> Result<(), String> {
    let shortcut = parse_shortcut(&hotkey)?;
    let app_handle = app.clone();
    let mode_clone = mode.clone();

    app.global_shortcut()
        .on_shortcut(shortcut, move |_app, _shortcut, event| {
            match mode_clone.as_str() {
                "push_to_talk" => {
                    if event.state() == ShortcutState::Pressed {
                        let _ = app_handle.emit("dictation://start", ());
                    } else {
                        let _ = app_handle.emit("dictation://stop", ());
                    }
                }
                _ => {
                    // toggle mode — fire only on key-down
                    if event.state() == ShortcutState::Pressed {
                        let _ = app_handle.emit("dictation://toggle", ());
                    }
                }
            }
        })
        .map_err(|e| format!("Failed to register hotkey '{hotkey}': {e}"))
}

/// Unregister a global hotkey by its string representation.
#[command]
pub fn unregister_hotkey(app: AppHandle, hotkey: String) -> Result<(), String> {
    let shortcut = parse_shortcut(&hotkey)?;
    app.global_shortcut()
        .unregister(shortcut)
        .map_err(|e| format!("Failed to unregister hotkey '{hotkey}': {e}"))
}

/// Register the global hotkey to toggle text polishing.
#[command]
pub fn register_polish_hotkey(app: AppHandle, hotkey: String) -> Result<(), String> {
    let shortcut = parse_shortcut(&hotkey)?;
    let app_handle = app.clone();

    app.global_shortcut()
        .on_shortcut(shortcut, move |_app, _shortcut, event| {
            if event.state() == ShortcutState::Pressed {
                println!("[Rust] Polish toggle hotkey pressed!");
                let handle = app_handle.clone();
                tauri::async_runtime::spawn(async move {
                    if let Ok(mut config) = super::config::get_config() {
                        let current_polish = config.get("enable_polish")
                            .and_then(|v| v.as_bool())
                            .unwrap_or(false);
                        let new_polish = !current_polish;

                        if let Some(obj) = config.as_object_mut() {
                            obj.insert("enable_polish".to_string(), serde_json::Value::Bool(new_polish));
                        }

                        if let Err(e) = super::config::save_config(handle.clone(), config) {
                            eprintln!("[Rust] Failed to save config on hotkey toggle: {}", e);
                        } else {
                            println!("[Rust] Polish toggled to: {}", new_polish);
                            let _ = handle.emit("dictation://polish-toggled", new_polish);
                        }
                    }
                });
            }
        })
        .map_err(|e| format!("Failed to register polish hotkey '{hotkey}': {e}"))
}

/// Unregister the global hotkey to toggle text polishing.
#[command]
pub fn unregister_polish_hotkey(app: AppHandle, hotkey: String) -> Result<(), String> {
    let shortcut = parse_shortcut(&hotkey)?;
    app.global_shortcut()
        .unregister(shortcut)
        .map_err(|e| format!("Failed to unregister polish hotkey '{hotkey}': {e}"))
}
