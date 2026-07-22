// src-tauri/src/commands/config.rs
//! Config management — reads/writes %APPDATA%\DictateAnywhere\config.json.
//! Schema is deliberately kept identical to the Python Config dataclass so
//! existing user configs load without migration.

use std::path::PathBuf;
use serde_json::Value;
use tauri::{command, AppHandle, Manager};

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

    // ── Show/hide, resize and reposition floating widget if configured ──
    if let Some(widget) = app.get_webview_window("floating-widget") {
        if let Some(show_widget) = config.get("show_floating_widget").and_then(|v| v.as_bool()) {
            if show_widget {
                let _ = widget.show();
            } else {
                let _ = widget.hide();
            }
        }

        if let Some(widget_size) = config.get("widget_size").and_then(|v| v.as_f64()) {
            let _ = widget.set_size(tauri::Size::Logical(tauri::LogicalSize::new(widget_size, widget_size)));
            
            if let Ok(Some(monitor)) = widget.current_monitor() {
                let scale_factor = monitor.scale_factor();
                let screen_w = monitor.size().width;
                let screen_h = monitor.size().height;
                
                let widget_w = (widget_size * scale_factor) as u32;
                let widget_h = (widget_size * scale_factor) as u32;
                
                // Place 60px (logical) from right, 140px (logical) from bottom
                let x = screen_w.saturating_sub(widget_w).saturating_sub((60.0 * scale_factor) as u32);
                let y = screen_h.saturating_sub(widget_h).saturating_sub((140.0 * scale_factor) as u32);
                
                let _ = widget.set_position(tauri::Position::Physical(tauri::PhysicalPosition::new(x as i32, y as i32)));
            }
        }
    }

    // 3. Emit config changed event
    use tauri::Emitter;
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

/// Open a native Windows file dialogue using a PowerShell helper.
#[command]
pub fn select_file() -> Result<Option<String>, String> {
    let output = std::process::Command::new("powershell")
        .args(&[
            "-NoProfile",
            "-Command",
            "[System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms') | Out-Null; $g = New-Object System.Windows.Forms.OpenFileDialog; $g.Title = 'Select Application or File'; $g.Filter = 'Executable Files (*.exe)|*.exe|All Files (*.*)|*.*'; if ($g.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { $g.FileName }",
        ])
        .output()
        .map_err(|e| format!("Failed to run file dialogue: {e}"))?;

    let path = String::from_utf8_lossy(&output.stdout).trim().to_string();
    if path.is_empty() {
        Ok(None)
    } else {
        Ok(Some(path))
    }
}

/// Write text to a file chosen by the user via a native Windows SaveFileDialog.
#[command]
pub fn export_text_file(text: String, default_filename: String) -> Result<Option<String>, String> {
    let escaped_default = default_filename.replace("'", "''");
    let ps_script = format!(
        "[System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms') | Out-Null; \
         $g = New-Object System.Windows.Forms.SaveFileDialog; \
         $g.Title = 'Export Transcription History'; \
         $g.Filter = 'Text Files (*.txt)|*.txt|All Files (*.*)|*.*'; \
         $g.FileName = '{}'; \
         if ($g.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {{ $g.FileName }}",
        escaped_default
    );

    let output = std::process::Command::new("powershell")
        .args(&[
            "-NoProfile",
            "-Command",
            &ps_script,
        ])
        .output()
        .map_err(|e| format!("Failed to run file dialogue: {e}"))?;

    let path = String::from_utf8_lossy(&output.stdout).trim().to_string();
    if path.is_empty() {
        Ok(None)
    } else {
        std::fs::write(&path, text)
            .map_err(|e| format!("Failed to write export file: {e}"))?;
        Ok(Some(path))
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
