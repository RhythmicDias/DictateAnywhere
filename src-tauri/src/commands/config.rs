// src-tauri/src/commands/config.rs
//! Config management — reads/writes %APPDATA%\DictateAnywhere\config.json.
//! Schema is deliberately kept identical to the Python Config dataclass so
//! existing user configs load without migration.

use std::path::PathBuf;
use std::sync::atomic::{AtomicI32, Ordering};
use serde_json::Value;
use tauri::{command, AppHandle, Emitter, Manager, WebviewWindow};

#[derive(Default)]
pub struct WidgetMenuState {
    pub offset_x: AtomicI32,
    pub offset_y: AtomicI32,
}

fn set_widget_bounds(widget: &WebviewWindow, x: i32, y: i32, w: u32, h: u32) {
    #[cfg(target_os = "windows")]
    if let Ok(hwnd) = widget.hwnd() {
        use windows::Win32::Foundation::HWND;
        use windows::Win32::UI::WindowsAndMessaging::{
            SetWindowPos, SWP_NOACTIVATE, SWP_NOZORDER,
        };
        unsafe {
            let _ = SetWindowPos(
                HWND(hwnd.0),
                None,
                x,
                y,
                w as i32,
                h as i32,
                SWP_NOZORDER | SWP_NOACTIVATE,
            );
        }
        return;
    }

    let _ = widget.set_position(tauri::Position::Physical(tauri::PhysicalPosition::new(x, y)));
    let _ = widget.set_size(tauri::Size::Physical(tauri::PhysicalSize::new(w, h)));
}

pub fn apply_widget_config_internal(app: &AppHandle, config: &Value) {
    if let Some(widget) = app.get_webview_window("floating-widget") {
        let menu_state = app.state::<WidgetMenuState>();
        let prev_ox = menu_state.offset_x.swap(0, Ordering::SeqCst);
        let prev_oy = menu_state.offset_y.swap(0, Ordering::SeqCst);

        if let Some(show_widget) = config.get("show_floating_widget").and_then(|v| v.as_bool()) {
            if show_widget {
                let _ = widget.show();
            } else {
                let _ = widget.hide();
            }
        }

        if let Some(always_on_top) = config.get("widget_always_on_top").and_then(|v| v.as_bool()) {
            let _ = widget.set_always_on_top(always_on_top);
        }

        if let Some(widget_size) = config.get("widget_size").and_then(|v| v.as_f64()) {
            let scale = widget.scale_factor().unwrap_or(1.0);
            let w_phys = (widget_size * scale).round() as u32;
            let cur_pos = widget
                .outer_position()
                .unwrap_or(tauri::PhysicalPosition::new(100, 100));
            let mut x = cur_pos.x + prev_ox;
            let mut y = cur_pos.y + prev_oy;

            if let Ok(Some(monitor)) = widget.current_monitor() {
                let mon_pos = monitor.position();
                let mon_size = monitor.size();
                let max_x = mon_pos.x + (mon_size.width as i32) - (w_phys as i32);
                let max_y = mon_pos.y + (mon_size.height as i32) - (w_phys as i32);
                x = x.clamp(mon_pos.x, max_x.max(mon_pos.x));
                y = y.clamp(mon_pos.y, max_y.max(mon_pos.y));
            }

            set_widget_bounds(&widget, x, y, w_phys, w_phys);
        }
    }
}

#[command]
pub fn preview_widget_config(app: AppHandle, config: Value) -> Result<(), String> {
    apply_widget_config_internal(&app, &config);
    let _ = app.emit("config://changed", config);
    Ok(())
}

#[command]
pub fn set_widget_menu_open(
    app: AppHandle,
    open: bool,
    widget_size: f64,
    click_x: f64,
    click_y: f64,
) -> Result<Value, String> {
    let widget = app
        .get_webview_window("floating-widget")
        .ok_or_else(|| "floating-widget window not found".to_string())?;
    let menu_state = app.state::<WidgetMenuState>();
    let scale = widget.scale_factor().unwrap_or(1.0);
    let cur_pos = widget.outer_position().map_err(|e| e.to_string())?;

    if !open {
        let prev_ox = menu_state.offset_x.swap(0, Ordering::SeqCst);
        let prev_oy = menu_state.offset_y.swap(0, Ordering::SeqCst);
        let mic_phys_x = cur_pos.x + prev_ox;
        let mic_phys_y = cur_pos.y + prev_oy;
        let w_phys = (widget_size * scale).round() as u32;
        set_widget_bounds(&widget, mic_phys_x, mic_phys_y, w_phys, w_phys);
        return Ok(serde_json::json!({
            "mic_x": 0.0,
            "mic_y": 0.0,
            "menu_x": 0.0,
            "menu_y": 0.0
        }));
    }

    let prev_ox = menu_state.offset_x.load(Ordering::SeqCst);
    let prev_oy = menu_state.offset_y.load(Ordering::SeqCst);
    let mic_phys_x = cur_pos.x + prev_ox;
    let mic_phys_y = cur_pos.y + prev_oy;

    const MENU_W: f64 = 180.0;
    const MENU_H: f64 = 200.0;
    const PAD: f64 = 16.0;

    let mut menu_x = click_x.clamp(0.0, widget_size);
    let mut menu_y = click_y.clamp(0.0, widget_size);

    if let Ok(Some(monitor)) = widget.current_monitor() {
        let mon_pos = monitor.position();
        let mon_size = monitor.size();
        let mon_left = (mon_pos.x as f64) / scale;
        let mon_top = (mon_pos.y as f64) / scale;
        let mon_right = mon_left + (mon_size.width as f64) / scale;
        let mon_bottom = mon_top + (mon_size.height as f64) / scale - 48.0;

        let mic_log_x = (mic_phys_x as f64) / scale;
        let mic_log_y = (mic_phys_y as f64) / scale;

        if mic_log_x + menu_x + MENU_W + PAD > mon_right {
            menu_x = (mon_right - PAD - MENU_W - mic_log_x).max(mon_left + PAD - mic_log_x);
        }
        if mic_log_y + menu_y + MENU_H + PAD > mon_bottom {
            menu_y = (mon_bottom - PAD - MENU_H - mic_log_y).max(mon_top + PAD - mic_log_y);
        }
    }

    let min_x = (0.0_f64).min(menu_x - PAD);
    let min_y = (0.0_f64).min(menu_y - PAD);
    let max_x = widget_size.max(menu_x + MENU_W + PAD);
    let max_y = widget_size.max(menu_y + MENU_H + PAD);

    let win_log_w = max_x - min_x;
    let win_log_h = max_y - min_y;

    let mic_dom_x = -min_x;
    let mic_dom_y = -min_y;
    let menu_dom_x = menu_x - min_x;
    let menu_dom_y = menu_y - min_y;

    let new_ox = (mic_dom_x * scale).round() as i32;
    let new_oy = (mic_dom_y * scale).round() as i32;
    menu_state.offset_x.store(new_ox, Ordering::SeqCst);
    menu_state.offset_y.store(new_oy, Ordering::SeqCst);

    let new_win_x = mic_phys_x - new_ox;
    let new_win_y = mic_phys_y - new_oy;
    let new_win_w = (win_log_w * scale).round() as u32;
    let new_win_h = (win_log_h * scale).round() as u32;

    set_widget_bounds(&widget, new_win_x, new_win_y, new_win_w, new_win_h);
    let _ = widget.set_focus();

    Ok(serde_json::json!({
        "mic_x": mic_dom_x,
        "mic_y": mic_dom_y,
        "menu_x": menu_dom_x,
        "menu_y": menu_dom_y
    }))
}

fn config_path() -> PathBuf {
    let appdata = std::env::var("APPDATA")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("."));
    appdata.join("DictateAnywhere").join("config.json")
}

/// Return the full config as a JSON value.
/// Falls back to an empty object if the file doesn't exist yet.
#[command]
pub fn get_config() -> Result<Value, String> {
    let path = config_path();
    if !path.exists() {
        return Ok(serde_json::json!({}));
    }
    let text = std::fs::read_to_string(&path)
        .map_err(|e| format!("Failed to read config: {e}"))?;
    serde_json::from_str(&text).map_err(|e| format!("Config parse error: {e}"))
}

/// Write the config JSON directly and re-register hotkeys.
#[command]
pub fn save_config(app: AppHandle, config: Value) -> Result<(), String> {
    // 1. Read old config to identify old hotkeys to unregister
    let (old_hotkey, old_polish_hotkey) = if let Ok(old_cfg) = get_config() {
        let hk = old_cfg.get("hotkey").and_then(|v| v.as_str()).map(|s| s.to_string());
        let phk = old_cfg.get("polish_hotkey").and_then(|v| v.as_str()).map(|s| s.to_string());
        (hk, phk)
    } else {
        (None, None)
    };

    // 2. Persist new config to file directly
    let path = config_path();
    if let Some(dir) = path.parent() {
        std::fs::create_dir_all(dir)
            .map_err(|e| format!("Failed to create config dir: {e}"))?;
    }
    let text = serde_json::to_string_pretty(&config)
        .map_err(|e| format!("Config serialize error: {e}"))?;
    std::fs::write(&path, text)
        .map_err(|e| format!("Failed to write config: {e}"))?;

    // 3. Unregister old hotkeys
    if let Some(old) = old_hotkey {
        let _ = super::hotkey::unregister_hotkey(app.clone(), old);
    }
    if let Some(old_p) = old_polish_hotkey {
        let _ = super::hotkey::unregister_polish_hotkey(app.clone(), old_p);
    }

    // ── Show/hide, resize and apply floating widget config ──
    apply_widget_config_internal(&app, &config);

    // 3. Emit config changed event
    let _ = app.emit("config://changed", config.clone());

    // 4. Register new hotkey
    let new_hotkey = config.get("hotkey")
        .and_then(|v| v.as_str())
        .unwrap_or("ctrl+alt+d")
        .to_string();
    let new_mode = config.get("hotkey_mode")
        .and_then(|v| v.as_str())
        .unwrap_or("toggle")
        .to_string();
    if let Err(e) = super::hotkey::register_hotkey(app.clone(), new_hotkey.clone(), new_mode) {
        eprintln!("[Rust] Failed to register new hotkey '{}': {}", new_hotkey, e);
    }

    // 5. Register new polish hotkey
    let new_p_hotkey = config.get("polish_hotkey")
        .and_then(|v| v.as_str())
        .unwrap_or("ctrl+alt+p")
        .to_string();
    if let Err(e) = super::hotkey::register_polish_hotkey(app, new_p_hotkey.clone()) {
        eprintln!("[Rust] Failed to register new polish hotkey '{}': {}", new_p_hotkey, e);
    }

    Ok(())
}

fn corrections_path() -> PathBuf {
    let appdata = std::env::var("APPDATA")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("."));
    appdata.join("DictateAnywhere").join("corrections.json")
}

/// Return the full corrections list as a JSON value.
/// Falls back to an empty array if the file doesn't exist yet.
#[command]
pub fn get_corrections() -> Result<Value, String> {
    let path = corrections_path();
    if !path.exists() {
        return Ok(serde_json::json!([]));
    }
    let text = std::fs::read_to_string(&path)
        .map_err(|e| format!("Failed to read corrections: {e}"))?;
    serde_json::from_str(&text).map_err(|e| format!("Corrections parse error: {e}"))
}

/// Write the corrections JSON directly.
#[command]
pub fn save_corrections(corrections: Value) -> Result<(), String> {
    let path = corrections_path();
    if let Some(dir) = path.parent() {
        std::fs::create_dir_all(dir)
            .map_err(|e| format!("Failed to create config dir: {e}"))?;
    }
    let text = serde_json::to_string_pretty(&corrections)
        .map_err(|e| format!("Corrections serialize error: {e}"))?;
    std::fs::write(&path, text)
        .map_err(|e| format!("Failed to write corrections: {e}"))?;
    Ok(())
}

/// Open a native Windows file dialogue using rfd (Common Item Dialog).
#[command]
pub async fn select_file() -> Result<Option<String>, String> {
    let file = rfd::AsyncFileDialog::new()
        .add_filter("Executable Files (*.exe)", &["exe"])
        .add_filter("All Files (*.*)", &["*"])
        .set_title("Select Application or File")
        .pick_file()
        .await;

    Ok(file.map(|f| f.path().to_string_lossy().to_string()))
}

/// Write text to a file chosen by the user via native Windows SaveFileDialog.
#[command]
pub async fn export_text_file(text: String, default_filename: String) -> Result<Option<String>, String> {
    let file = rfd::AsyncFileDialog::new()
        .add_filter("Text Files (*.txt)", &["txt"])
        .add_filter("All Files (*.*)", &["*"])
        .set_title("Export Transcription History")
        .set_file_name(&default_filename)
        .save_file()
        .await;

    if let Some(handle) = file {
        let path = handle.path().to_path_buf();
        std::fs::write(&path, text).map_err(|e| format!("Failed to write export file: {e}"))?;
        Ok(Some(path.to_string_lossy().to_string()))
    } else {
        Ok(None)
    }
}

fn models_dir() -> PathBuf {
    let appdata = std::env::var("APPDATA")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("."));
    appdata.join("DictateAnywhere").join("models")
}

#[derive(serde::Serialize)]
pub struct ModelCacheInfo {
    name: String,
    size_mb: f64,
}

#[command]
pub fn get_cached_models() -> Result<Vec<ModelCacheInfo>, String> {
    let dir = models_dir();
    let mut results = Vec::new();
    if !dir.exists() {
        return Ok(results);
    }
    
    let prefix = "models--Systran--faster-whisper-";
    
    let entries = std::fs::read_dir(&dir)
        .map_err(|e| format!("Failed to read models directory: {e}"))?;
        
    for entry in entries {
        let entry = entry.map_err(|e| format!("Failed to read directory entry: {e}"))?;
        let path = entry.path();
        if path.is_dir() {
            if let Some(folder_name) = path.file_name().and_then(|s| s.to_str()) {
                if folder_name.starts_with(prefix) {
                    let model_name = folder_name[prefix.len()..].to_string();
                    let size_bytes = get_dir_size(&path)?;
                    let size_mb = (size_bytes as f64) / (1024.0 * 1024.0);
                    results.push(ModelCacheInfo {
                        name: model_name,
                        size_mb,
                    });
                }
            }
        }
    }
    results.sort_by(|a, b| a.name.cmp(&b.name));
    Ok(results)
}

fn get_dir_size(path: &std::path::Path) -> Result<u64, String> {
    let mut total_size = 0;
    if path.is_dir() {
        for entry in std::fs::read_dir(path).map_err(|e| e.to_string())? {
            let entry = entry.map_err(|e| e.to_string())?;
            let path = entry.path();
            if path.is_dir() {
                total_size += get_dir_size(&path)?;
            } else {
                total_size += entry.metadata().map_err(|e| e.to_string())?.len();
            }
        }
    }
    Ok(total_size)
}

#[command]
pub fn delete_cached_model(name: String) -> Result<(), String> {
    let dir = models_dir();
    let folder_name = format!("models--Systran--faster-whisper-{}", name);
    let target = dir.join(folder_name);
    if target.exists() && target.is_dir() {
        std::fs::remove_dir_all(target)
            .map_err(|e| format!("Failed to delete model directory: {e}"))?;
    }
    Ok(())
}

#[derive(serde::Deserialize)]
struct OllamaResponse {
    models: Option<Vec<OllamaModel>>,
}

#[derive(serde::Deserialize)]
struct OllamaModel {
    name: String,
}

#[command]
pub async fn get_ollama_models(url: String) -> Result<Vec<String>, String> {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(3))
        .build()
        .map_err(|e| format!("Failed to build HTTP client: {e}"))?;
        
    let clean_url = url.trim_end_matches('/');
    let target_url = format!("{}/api/tags", clean_url);
    
    let resp = client.get(&target_url)
        .send()
        .await
        .map_err(|e| format!("Ollama server connection failed: {e}"))?;
        
    if !resp.status().is_success() {
        return Err(format!("Server returned error status: {}", resp.status()));
    }
    
    let data: OllamaResponse = resp.json()
        .await
        .map_err(|e| format!("Failed to parse Ollama models response: {e}"))?;
        
    let mut names = Vec::new();
    if let Some(models) = data.models {
        for m in models {
            names.push(m.name);
        }
    }
    names.sort();
    Ok(names)
}

#[derive(serde::Deserialize)]
struct GithubRelease {
    tag_name: String,
    html_url: String,
}

#[command]
pub async fn check_for_updates(app: AppHandle) -> Result<Value, String> {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(10))
        .build()
        .map_err(|e| format!("Failed to build HTTP client: {e}"))?;
        
    let resp = client.get("https://api.github.com/repos/RhythmicDias/DictateAnywhere/releases/latest")
        .header("User-Agent", "DictateAnywhere-UpdateChecker/2.0")
        .header("Accept", "application/vnd.github.v3+json")
        .send()
        .await
        .map_err(|e| format!("GitHub API request failed: {e}"))?;
        
    if !resp.status().is_success() {
        return Err(format!("GitHub API returned error: {}", resp.status()));
    }
    
    let data: GithubRelease = resp.json()
        .await
        .map_err(|e| format!("Failed to parse GitHub release response: {e}"))?;
        
    let current_version = app.package_info().version.to_string();
    let latest_version = data.tag_name.trim().trim_start_matches('v').trim_start_matches('V').to_string();
    
    let is_newer = is_version_newer(&current_version, &latest_version);
    
    Ok(serde_json::json!({
        "latest": latest_version,
        "url": data.html_url,
        "is_newer": is_newer,
        "current": current_version,
    }))
}

fn is_version_newer(current: &str, latest: &str) -> bool {
    let curr_parts: Vec<u32> = current.split('.')
        .map(|s| s.parse().unwrap_or(0))
        .collect();
    let late_parts: Vec<u32> = latest.split('.')
        .map(|s| s.parse().unwrap_or(0))
        .collect();
        
    for i in 0..std::cmp::max(curr_parts.len(), late_parts.len()) {
        let c = curr_parts.get(i).cloned().unwrap_or(0);
        let l = late_parts.get(i).cloned().unwrap_or(0);
        if l > c {
            return true;
        } else if c > l {
            return false;
        }
    }
    false
}

#[command]
pub fn open_config_folder() -> Result<(), String> {
    let path = config_path();
    let folder = path.parent().ok_or("No config parent directory")?;
    std::process::Command::new("explorer")
        .arg(folder)
        .spawn()
        .map_err(|e| format!("Failed to open config folder: {e}"))?;
    Ok(())
}
