// src-tauri/src/lib.rs
//! DictateAnywhere — Tauri v2 application root.
//!
//! Sets up:
//!   - System tray (primary entry point; app starts hidden)
//!   - Global hotkey (Ctrl+Alt+D by default)
//!   - Multi-window declarations (floating-widget, settings, preview, history)
//!   - Tauri command handlers

pub mod commands;
pub mod models;

use tauri::{
    menu::{Menu, MenuItem, PredefinedMenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Emitter, Listener, Manager, Runtime,
};
// Unused imports from tauri_plugin_global_shortcut removed

use commands::config::{
    get_config, save_config, get_corrections, save_corrections, select_file, export_text_file,
    get_cached_models, delete_cached_model, get_ollama_models, check_for_updates, open_config_folder
};
use commands::hotkey::{register_hotkey, unregister_hotkey, register_polish_hotkey, unregister_polish_hotkey};
use commands::sidecar::{SidecarState, start_sidecar, start_sidecar_with_state, send_to_sidecar, send_to_sidecar_owned, stop_sidecar, list_audio_devices, restart_sidecar_internal};
use commands::injection::inject_text;
use commands::storage::{get_api_key, set_api_key};

/// Emit a Tauri event to all windows.
pub fn emit_all<R: Runtime, S: serde::Serialize + Clone>(
    app: &AppHandle<R>,
    event: &str,
    payload: S,
) {
    let _ = app.emit(event, payload);
}

/// Get or create a named window; show it if already exists.
fn show_window(app: &AppHandle, label: &str) {
    if let Some(win) = app.get_webview_window(label) {
        let _ = win.show();
        let _ = win.set_focus();
    }
}

fn toggle_window(app: &AppHandle, label: &str) {
    if let Some(win) = app.get_webview_window(label) {
        if win.is_visible().unwrap_or(false) {
            let _ = win.hide();
        } else {
            let _ = win.show();
            let _ = win.set_focus();
        }
    }
}

/// Build the tray icon context menu.
fn build_tray_menu(app: &AppHandle) -> tauri::Result<Menu<tauri::Wry>> {
    let start = MenuItem::with_id(app, "start", "Start Dictation", true, None::<&str>)?;
    let stop = MenuItem::with_id(app, "stop", "Stop Dictation", false, None::<&str>)?;
    let sep1 = PredefinedMenuItem::separator(app)?;
    let toggle_widget =
        MenuItem::with_id(app, "toggle_widget", "Toggle Floating Button", true, None::<&str>)?;
    let toggle_preview =
        MenuItem::with_id(app, "toggle_preview", "Toggle Preview Overlay", true, None::<&str>)?;
    let history = MenuItem::with_id(app, "history", "Session History…", true, None::<&str>)?;
    let settings = MenuItem::with_id(app, "settings", "Settings…", true, None::<&str>)?;
    let sep2 = PredefinedMenuItem::separator(app)?;
    let quit = MenuItem::with_id(app, "quit", "Quit DictateAnywhere", true, None::<&str>)?;

    Menu::with_items(
        app,
        &[
            &start,
            &stop,
            &sep1,
            &toggle_widget,
            &toggle_preview,
            &history,
            &settings,
            &sep2,
            &quit,
        ],
    )
}

/// Register the configured global hotkey at startup.
fn setup_default_hotkey(app: &AppHandle) {
    let (hotkey_str, mode_str) = if let Ok(cfg) = get_config() {
        let hotkey = cfg.get("hotkey")
            .and_then(|v| v.as_str())
            .unwrap_or("ctrl+alt+d")
            .to_string();
        let mode = cfg.get("hotkey_mode")
            .and_then(|v| v.as_str())
            .unwrap_or("toggle")
            .to_string();
        (hotkey, mode)
    } else {
        ("ctrl+alt+d".to_string(), "toggle".to_string())
    };

    println!("[Rust] Registering startup hotkey '{}' in mode '{}'", hotkey_str, mode_str);
    if let Err(e) = commands::hotkey::register_hotkey(app.clone(), hotkey_str.clone(), mode_str.clone()) {
        eprintln!("[Rust] Failed to register startup hotkey '{}': {}", hotkey_str, e);
    }
}

/// Register the configured polish hotkey at startup.
fn setup_polish_hotkey(app: &AppHandle) {
    let hotkey_str = if let Ok(cfg) = get_config() {
        cfg.get("polish_hotkey")
            .and_then(|v| v.as_str())
            .unwrap_or("ctrl+alt+p")
            .to_string()
    } else {
        "ctrl+alt+p".to_string()
    };

    println!("[Rust] Registering startup polish hotkey '{}'", hotkey_str);
    if let Err(e) = commands::hotkey::register_polish_hotkey(app.clone(), hotkey_str.clone()) {
        eprintln!("[Rust] Failed to register startup polish hotkey '{}': {}", hotkey_str, e);
    }
}

/// Windows-only: spin up a background thread that watches for suspend/resume events
/// via a message-only window receiving WM_POWERBROADCAST.
/// On resume, it emits the internal "system://wake" event so the Tauri side can recover.
#[cfg(target_os = "windows")]
fn start_power_broadcast_listener(app: AppHandle) {
    use windows::Win32::Foundation::{HWND, LPARAM, LRESULT, WPARAM};
    use windows::Win32::UI::WindowsAndMessaging::{
        CreateWindowExW, DefWindowProcW, DispatchMessageW, GetMessageW, HMENU,
        MSG, RegisterClassExW, WINDOW_EX_STYLE, WM_POWERBROADCAST, WNDCLASSEXW,
        WS_OVERLAPPED, CS_HREDRAW, CS_VREDRAW,
    };
    use windows::core::PCWSTR;

    // PBT_APMRESUMEAUTOMATIC = 0x12 — stable Win32 constant (unchanged since Win98).
    // Defined locally to avoid depending on a specific windows-crate feature gate.
    const PBT_APMRESUMEAUTOMATIC: u32 = 0x0012;

    std::thread::Builder::new()
        .name("power-broadcast".into())
        .spawn(move || unsafe {
            // Wide null-terminated class name — must outlive RegisterClassEx + CreateWindow
            let class_name: Vec<u16> = "DictateAnywhereWake\0".encode_utf16().collect();

            extern "system" fn wnd_proc(
                hwnd: HWND,
                msg: u32,
                wparam: WPARAM,
                lparam: LPARAM,
            ) -> LRESULT {
                // Safety: DefWindowProcW is always safe to call as a default handler
                unsafe { DefWindowProcW(hwnd, msg, wparam, lparam) }
            }

            let wc = WNDCLASSEXW {
                cbSize: std::mem::size_of::<WNDCLASSEXW>() as u32,
                style: CS_HREDRAW | CS_VREDRAW,
                lpfnWndProc: Some(wnd_proc),
                lpszClassName: PCWSTR(class_name.as_ptr()),
                ..Default::default()
            };
            let _ = RegisterClassExW(&wc); // ignore error if already registered

            // HWND_MESSAGE (-3) = message-only window (no desktop visibility)
            let hwnd_message = HWND(-3isize as *mut core::ffi::c_void);
            let hwnd = match CreateWindowExW(
                WINDOW_EX_STYLE::default(),
                PCWSTR(class_name.as_ptr()),
                PCWSTR::null(),
                WS_OVERLAPPED,
                0, 0, 0, 0,
                hwnd_message,
                HMENU::default(),
                None,
                None,
            ) {
                Ok(h) => h,
                Err(e) => {
                    eprintln!("[PowerBroadcast] Failed to create message window: {:?}", e);
                    return;
                }
            };

            let mut msg = MSG::default();
            loop {
                // GetMessageW returns BOOL; 0 = WM_QUIT, -1 = error
                let ret = GetMessageW(&mut msg, hwnd, 0, 0);
                match ret.0 {
                    0 => break,  // WM_QUIT
                    -1 => break, // error
                    _ => {}
                }

                if msg.message == WM_POWERBROADCAST {
                    // WPARAM for PBT_APMRESUMEAUTOMATIC == 0x12
                    if msg.wParam.0 as u32 == PBT_APMRESUMEAUTOMATIC {
                        println!("[PowerBroadcast] System resumed from sleep — emitting system://wake");
                        let _ = app.emit("system://wake", ());
                    }
                }
                DispatchMessageW(&msg);
            }
        })
        .expect("Failed to spawn power-broadcast thread");
}

#[cfg(not(target_os = "windows"))]
fn start_power_broadcast_listener(_app: AppHandle) {
    // No-op on non-Windows platforms
}


/// Called on system wake: re-shows the floating widget, re-registers hotkeys,
/// and kicks off a sidecar restart if it died during sleep.
fn handle_system_wake(app: &AppHandle) {
    println!("[Wake] Recovering after sleep...");

    // 1. Re-show and re-assert always-on-top on the floating widget
    if let Some(widget) = app.get_webview_window("floating-widget") {
        // Read config to check if widget should be visible
        let should_show = if let Ok(cfg) = get_config() {
            cfg.get("show_floating_widget")
                .and_then(|v| v.as_bool())
                .unwrap_or(true)
        } else {
            true
        };

        if should_show {
            let _ = widget.show();
            let _ = widget.set_always_on_top(true);
            println!("[Wake] Floating widget re-shown.");
        }
    }

    // 2. Re-register hotkeys (Windows may drop them on session lock/display change)
    // Unregister first to avoid "already registered" errors
    {
        use tauri_plugin_global_shortcut::GlobalShortcutExt;
        let _ = app.global_shortcut().unregister_all();
    }
    setup_default_hotkey(app);
    setup_polish_hotkey(app);
    println!("[Wake] Hotkeys re-registered.");

    // 3. Always restart the sidecar on system wake to ensure audio capture and device states are cleanly re-initialized
    println!("[Wake] Scheduling sidecar restart to recover audio devices...");
    let handle = app.clone();
    tauri::async_runtime::spawn(async move {
        // Give the OS a moment to fully restore network/GPU/audio after resume
        tokio::time::sleep(std::time::Duration::from_secs(2)).await;
        restart_sidecar_internal(handle).await;
    });
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(SidecarState::default())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .plugin(tauri_plugin_shell::init())
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                let label = window.label();
                if label == "settings" || label == "history" {
                    api.prevent_close();
                    let _ = window.hide();
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            get_config,
            save_config,
            get_corrections,
            save_corrections,
            select_file,
            export_text_file,
            register_hotkey,
            unregister_hotkey,
            register_polish_hotkey,
            unregister_polish_hotkey,
            start_sidecar,
            send_to_sidecar,
            stop_sidecar,
            list_audio_devices,
            inject_text,
            get_api_key,
            set_api_key,
            get_cached_models,
            delete_cached_model,
            get_ollama_models,
            check_for_updates,
            open_config_folder,
        ])
        .setup(|app| {
            // ── Build tray menu ─────────────────────────────────────────────
            let menu = build_tray_menu(app.handle())?;

            // ── Load tray icon from bundled asset ───────────────────────────
            let tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .tooltip("DictateAnywhere")
                .on_menu_event({
                    let handle = app.handle().clone();
                    move |app, event| match event.id().as_ref() {
                        "start" => {
                            let _ = app.emit("dictation://start", ());
                        }
                        "stop" => {
                            let _ = app.emit("dictation://stop", ());
                        }
                        "toggle_widget" => {
                            toggle_window(&handle, "floating-widget");
                        }
                        "toggle_preview" => {
                            toggle_window(&handle, "preview");
                        }
                        "settings" => {
                            show_window(&handle, "settings");
                        }
                        "history" => {
                            show_window(&handle, "history");
                        }
                        "quit" => {
                            app.exit(0);
                        }
                        _ => {}
                    }
                })
                .on_tray_icon_event(|_tray, event| {
                    // Left-click on tray: no-op (menu appears on right-click by default)
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        // Could toggle floating widget here if desired
                    }
                })
                .build(app)?;

            // Keep tray alive for the app lifetime
            app.manage(tray);

            // ── Load config values for widget sizing & opacity ───────────────────
            let (widget_size, _widget_opacity, show_floating_widget) = if let Ok(cfg) = get_config() {
                let s = cfg.get("widget_size")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(64.0);
                let o = cfg.get("widget_opacity")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(0.85);
                let show = cfg.get("show_floating_widget")
                    .and_then(|v| v.as_bool())
                    .unwrap_or(true);
                (s, o, show)
            } else {
                (64.0, 0.85, true)
            };

            // ── Position and show windows programmatically ───────────────────
            if let Ok(Some(monitor)) = app.primary_monitor() {
                let size = monitor.size();
                let scale_factor = monitor.scale_factor();
                let screen_w = size.width;
                let screen_h = size.height;

                // 1. Position Floating Widget near right-lower corner:
                // Scale physical dimensions correctly.
                if let Some(widget) = app.get_webview_window("floating-widget") {
                    let _ = widget.set_size(tauri::Size::Logical(tauri::LogicalSize::new(widget_size, widget_size)));
                    
                    
                    let widget_w = (widget_size * scale_factor) as u32;
                    let widget_h = (widget_size * scale_factor) as u32;
                    
                    // Place 60px (logical) from right, 140px (logical) from bottom (above taskbar)
                    let x = screen_w.saturating_sub(widget_w).saturating_sub((60.0 * scale_factor) as u32);
                    let y = screen_h.saturating_sub(widget_h).saturating_sub((140.0 * scale_factor) as u32);
                    
                    let _ = widget.set_position(tauri::Position::Physical(tauri::PhysicalPosition::new(x as i32, y as i32)));
                    if show_floating_widget {
                        let _ = widget.show();
                    } else {
                        let _ = widget.hide();
                    }
                }

                // 2. Position Preview Overlay at center-bottom:
                // Width 340, height 80.
                if let Some(preview) = app.get_webview_window("preview") {
                    let preview_w = (480.0 * scale_factor) as u32;
                    let preview_h = (110.0 * scale_factor) as u32;
                    
                    let x = screen_w.saturating_sub(preview_w) / 2;
                    // Place 140px (logical) from bottom (above taskbar)
                    let y = screen_h.saturating_sub(preview_h).saturating_sub((140.0 * scale_factor) as u32);
                    
                    let _ = preview.set_position(tauri::Position::Physical(tauri::PhysicalPosition::new(x as i32, y as i32)));
                }
            } else {
                // Fallback if monitor details are unavailable
                if let Some(widget) = app.get_webview_window("floating-widget") {
                    if show_floating_widget {
                        let _ = widget.show();
                    } else {
                        let _ = widget.hide();
                    }
                }
            }

            // ── Register default hotkey ──────────────────────────────────────
            setup_default_hotkey(app.handle());
            setup_polish_hotkey(app.handle());

            // ── Register window management listeners ────────────────────────
            let app_handle = app.handle().clone();
            app.listen("window://show", move |event| {
                #[derive(serde::Deserialize)]
                struct WindowPayload { label: String }
                if let Ok(p) = serde_json::from_str::<WindowPayload>(event.payload()) {
                    show_window(&app_handle, &p.label);
                }
            });

            let app_handle = app.handle().clone();
            app.listen("window://toggle", move |event| {
                #[derive(serde::Deserialize)]
                struct WindowPayload { label: String }
                if let Ok(p) = serde_json::from_str::<WindowPayload>(event.payload()) {
                    toggle_window(&app_handle, &p.label);
                }
            });

            let app_handle = app.handle().clone();
            app.listen("dictation://start", move |_event| {
                let state = app_handle.state::<SidecarState>();
                if !state.ready.load(std::sync::atomic::Ordering::SeqCst) {
                    println!("[Rust] Ignoring dictation://start: Sidecar is not ready yet!");
                    return;
                }
                println!("[Rust] Received dictation://start event");
                let handle = app_handle.clone();
                tauri::async_runtime::spawn(async move {
                    let config = match get_config() {
                        Ok(cfg) => cfg,
                        Err(e) => {
                            eprintln!("[Rust] Failed to load config: {}", e);
                            serde_json::json!({})
                        }
                    };
                    
                    // Fetch keys from keyring securely
                    let azure_key = get_api_key("azure".to_string()).ok().flatten().unwrap_or_default();
                    let gemini_key = get_api_key("gemini".to_string()).ok().flatten().unwrap_or_default();
                    let sarvam_key = get_api_key("sarvam".to_string()).ok().flatten().unwrap_or_default();
                    let openrouter_key = get_api_key("openrouter".to_string()).ok().flatten().unwrap_or_default();
                    let groq_key = get_api_key("groq".to_string()).ok().flatten().unwrap_or_default();

                    let api_keys = serde_json::json!({
                        "azure": azure_key,
                        "gemini": gemini_key,
                        "sarvam": sarvam_key,
                        "openrouter": openrouter_key,
                        "groq": groq_key
                    });

                    let payload = serde_json::json!({
                        "cmd": "start",
                        "config": config,
                        "api_keys": api_keys
                    });
                    println!("[Rust] Sending start command to sidecar");
                    let state = (*handle.state::<SidecarState>()).clone();
                    if let Err(e) = send_to_sidecar_owned(state, payload) {
                        eprintln!("[Rust] Error sending start command to sidecar: {}", e);
                    }
                });
            });

            let app_handle = app.handle().clone();
            app.listen("dictation://stop", move |_event| {
                let state = app_handle.state::<SidecarState>();
                if !state.ready.load(std::sync::atomic::Ordering::SeqCst) {
                    return;
                }
                println!("[Rust] Received dictation://stop event");
                let handle = app_handle.clone();
                tauri::async_runtime::spawn(async move {
                    let state = (*handle.state::<SidecarState>()).clone();
                    let payload = serde_json::json!({ "cmd": "stop" });
                    println!("[Rust] Sending stop command to sidecar");
                    if let Err(e) = send_to_sidecar_owned(state, payload) {
                        eprintln!("[Rust] Error sending stop command to sidecar: {}", e);
                    }
                });
            });

            // ── Start sidecar process (sync — no spawn needed) ───────────────
            let state = (*app.state::<SidecarState>()).clone();
            if let Err(e) = start_sidecar_with_state(app.handle().clone(), state) {
                eprintln!("Failed to auto-start sidecar: {}", e);
            }

            // ── Sleep/Wake recovery listener ────────────────────────────────
            let app_handle = app.handle().clone();
            app.listen("system://wake", move |_event| {
                handle_system_wake(&app_handle);
            });

            // ── Start Windows power broadcast monitor (message-only window) ──
            start_power_broadcast_listener(app.handle().clone());

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running DictateAnywhere");
}
