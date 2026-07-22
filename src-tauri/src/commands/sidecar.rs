// src-tauri/src/commands/sidecar.rs
use std::sync::{Arc, Mutex};
use std::sync::atomic::{AtomicBool, Ordering};
use tauri::{AppHandle, Emitter, State, Manager};
use tauri_plugin_shell::process::{CommandEvent, CommandChild};
use tauri_plugin_shell::ShellExt;
use serde_json::Value;

/// Application-managed sidecar state.
///
/// Fields are `Arc`-wrapped so the struct is cheaply `Clone + Send + Sync`.
/// `State<'_, SidecarState>` has a non-`'static` lifetime and cannot be moved
/// into spawned futures. Instead, deref and clone: `(*state).clone()`.
#[derive(Clone)]
pub struct SidecarState {
    pub child: Arc<Mutex<Option<CommandChild>>>,
    pub ready: Arc<AtomicBool>,
}

impl Default for SidecarState {
    fn default() -> Self {
        Self {
            child: Arc::new(Mutex::new(None)),
            ready: Arc::new(AtomicBool::new(false)),
        }
    }
}

// ── Public Tauri commands ───────────────────────────────────────────────────

#[tauri::command]
pub async fn start_sidecar(
    app: AppHandle,
    state: State<'_, SidecarState>,
) -> Result<(), String> {
    // (*state) derefs State<'_, SidecarState> → SidecarState, then .clone() gives owned copy
    start_sidecar_with_state(app, (*state).clone())
}

#[tauri::command]
pub async fn send_to_sidecar(
    state: State<'_, SidecarState>,
    message: Value,
) -> Result<(), String> {
    send_to_sidecar_owned((*state).clone(), message)
}

#[tauri::command]
pub async fn stop_sidecar(state: State<'_, SidecarState>) -> Result<(), String> {
    let mut guard = state.child.lock().unwrap();
    state.ready.store(false, Ordering::SeqCst);
    if let Some(mut child) = guard.take() {
        let _ = child.write(b"{\"cmd\":\"stop\"}\n");
        let _ = child.kill();
    }
    Ok(())
}

// ── Internal helpers ────────────────────────────────────────────────────────

/// Spawn the sidecar process and start the async reader task.
///
/// This is a **synchronous** function — `Command::spawn()` (tauri_plugin_shell)
/// is a blocking OS call with no `.await`. Keeping this as a plain `fn` avoids
/// creating a non-`Send` future (caused by shell internals), which would
/// prevent it from being awaited inside `tauri::async_runtime::spawn`.
pub fn start_sidecar_with_state(app: AppHandle, state: SidecarState) -> Result<(), String> {
    {
        let mut guard = state.child.lock().unwrap();
        if guard.is_some() {
            return Ok(()); // Already running
        }
        state.ready.store(false, Ordering::SeqCst);

        let (mut rx, child) = app
            .shell()
            .sidecar("whisper_sidecar")
            .map_err(|e| format!("Failed to find sidecar: {e}"))?
            .spawn()
            .map_err(|e| format!("Failed to spawn sidecar: {e}"))?;

        *guard = Some(child);
        drop(guard); // Release lock before spawning the async reader

        // Async reader task — handles stdout/stderr/termination events
        let app_handle = app.clone();
        let sidecar_state = state.clone();
        tauri::async_runtime::spawn(async move {
            while let Some(event) = rx.recv().await {
                match event {
                    CommandEvent::Stdout(line_bytes) => {
                        if let Ok(line_str) = String::from_utf8(line_bytes) {
                            for line in line_str.lines() {
                                if let Ok(value) = serde_json::from_str::<Value>(line) {
                                    println!("[Sidecar] {:?}", value);
                                    let _ = app_handle.emit("dictation://sidecar-event", value.clone());

                                    if let Some(event_type) = value.get("type").and_then(|t| t.as_str()) {
                                        match event_type {
                                            "ready" => {
                                                println!("[Rust] Sidecar ready.");
                                                sidecar_state.ready.store(true, Ordering::SeqCst);
                                                let _ = app_handle.emit("dictation://state-changed", "idle");
                                            }
                                            "state" => {
                                                if let Some(s) = value.get("state").and_then(|s| s.as_str()) {
                                                    let _ = app_handle.emit("dictation://state-changed", s);

                                                    // Native handling: Show preview overlay window when recording starts
                                                    if s == "active" {
                                                        let show_preview = if let Ok(cfg) = super::config::get_config() {
                                                            cfg.get("show_preview_window")
                                                                .and_then(|v| v.as_bool())
                                                                .unwrap_or(true)
                                                        } else {
                                                            true
                                                        };
                                                        if show_preview {
                                                            if let Some(preview_win) = app_handle.get_webview_window("preview") {
                                                                let _ = preview_win.show();
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                            "audio_level" => {
                                                if let Some(rms) = value.get("rms").and_then(|r| r.as_f64()) {
                                                    let _ = app_handle.emit("dictation://audio-level", rms);
                                                }
                                            }
                                            "result" => {
                                                if let Some(text) = value.get("text").and_then(|t| t.as_str()) {
                                                    println!("Transcribed: {}", text);
                                                    let (method, delay) = if let Ok(cfg) = super::config::get_config() {
                                                        let m = cfg.get("inject_method").and_then(|v| v.as_str()).map(|s| s.to_string());
                                                        let d = cfg.get("inject_delay_ms").and_then(|v| v.as_u64());
                                                        (m, d)
                                                    } else {
                                                        (None, None)
                                                    };
                                                    if let Err(e) = super::injection::inject_text(text.to_string(), method, delay).await {
                                                         eprintln!("[Rust] Text injection failed: {}", e);
                                                         let _ = app_handle.emit("dictation://error", format!("Injection failed: {}", e));
                                                     }
                                                    let _ = app_handle.emit("dictation://transcription-result", value.clone());
                                                }
                                            }
                                            "error" => {
                                                if let Some(msg) = value.get("message").and_then(|m| m.as_str()) {
                                                    eprintln!("[Sidecar Error] {}", msg);
                                                    let _ = app_handle.emit("dictation://error", msg);
                                                }
                                            }
                                            _ => {}
                                        }
                                    }
                                }
                            }
                        }
                    }
                    CommandEvent::Stderr(line_bytes) => {
                        if let Ok(s) = String::from_utf8(line_bytes) {
                            for line in s.lines() {
                                eprintln!("[Sidecar Log] {}", line.trim());
                            }
                        }
                    }
                    CommandEvent::Terminated(status) => {
                        eprintln!("[Sidecar Terminated] {:?}", status);
                        sidecar_state.ready.store(false, Ordering::SeqCst);
                        let _ = app_handle.emit("dictation://state-changed", "loading");

                        // Clear stale handle so restart can proceed
                        { let mut g = sidecar_state.child.lock().unwrap(); *g = None; }

                        // Auto-restart after 2 s.
                        // Use std::thread (not async) to avoid Send constraints on the future.
                        let app_clone = app_handle.clone();
                        let state_clone = sidecar_state.clone();
                        std::thread::spawn(move || {
                            std::thread::sleep(std::time::Duration::from_secs(2));
                            if state_clone.child.lock().unwrap().is_none() {
                                eprintln!("[Sidecar] Auto-restarting...");
                                match start_sidecar_with_state(app_clone, state_clone) {
                                    Ok(_)  => println!("[Sidecar] Auto-restart OK."),
                                    Err(e) => eprintln!("[Sidecar] Auto-restart failed: {}", e),
                                }
                            }
                        });

                        break;
                    }
                    _ => {}
                }
            }
        });
    }

    Ok(())
}

/// Write a JSON message to the sidecar's stdin.
///
/// Synchronous (`child.write` is a blocking OS write) — no `.await` needed.
pub fn send_to_sidecar_owned(state: SidecarState, message: Value) -> Result<(), String> {
    let mut guard = state.child.lock().unwrap();
    if let Some(child) = guard.as_mut() {
        let mut input = serde_json::to_string(&message).map_err(|e| e.to_string())?;
        input.push('\n');
        child.write(input.as_bytes()).map_err(|e| e.to_string())?;
        Ok(())
    } else {
        Err("Sidecar not running".to_string())
    }
}

/// Gracefully stop and restart the sidecar. Called from the system wake handler.
/// Async because it uses tokio::time::sleep for grace periods.
pub async fn restart_sidecar_internal(app: AppHandle) {
    let state = (*app.state::<SidecarState>()).clone();

    // Extract child before any .await (MutexGuard is not Send)
    let maybe_child = {
        let mut guard = state.child.lock().unwrap();
        state.ready.store(false, Ordering::SeqCst);
        guard.take()
    };

    if let Some(mut child) = maybe_child {
        let _ = child.write(b"{\"cmd\":\"stop\"}\n");
        tokio::time::sleep(std::time::Duration::from_millis(300)).await;
        let _ = child.kill();
    }

    // Let OS/GPU settle after sleep resume
    tokio::time::sleep(std::time::Duration::from_secs(1)).await;

    // start_sidecar_with_state is sync — no await needed
    match start_sidecar_with_state(app, state) {
        Ok(_)  => println!("[Sidecar] Restart after wake OK."),
        Err(e) => eprintln!("[Sidecar] Restart after wake failed: {}", e),
    }
}

#[tauri::command]
pub async fn list_audio_devices(app: AppHandle) -> Result<Value, String> {
    let output = app
        .shell()
        .sidecar("whisper_sidecar")
        .map_err(|e| format!("Failed to create sidecar command: {e}"))?
        .args(["--list-devices"])
        .output()
        .await
        .map_err(|e| format!("Failed to execute sidecar: {e}"))?;

    if !output.status.success() {
        return Err(format!("Sidecar error: {}", String::from_utf8_lossy(&output.stderr)));
    }

    let stdout_str = String::from_utf8(output.stdout)
        .map_err(|e| format!("Invalid UTF-8: {e}"))?;

    serde_json::from_str(&stdout_str)
        .map_err(|e| format!("Failed to parse JSON: {e}"))
}
