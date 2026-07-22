// src-tauri/src/commands/injection.rs
//! Text injection command handlers using native Win32 APIs via the windows crate.
//! Replicates the Python text_injector.py functionality.

use std::ptr::copy_nonoverlapping;
use std::thread;
use std::time::Duration;
use windows::Win32::Foundation::{HANDLE, HWND, HGLOBAL};
use windows::Win32::System::DataExchange::{
    OpenClipboard, CloseClipboard, EmptyClipboard, SetClipboardData, GetClipboardData, IsClipboardFormatAvailable
};
use windows::Win32::System::Memory::{
    GlobalAlloc, GlobalLock, GlobalUnlock, GMEM_MOVEABLE
};
use windows::Win32::UI::Input::KeyboardAndMouse::{
    GetAsyncKeyState, SendInput, INPUT, INPUT_0, KEYBDINPUT, VIRTUAL_KEY,
    INPUT_KEYBOARD, KEYEVENTF_KEYUP, KEYEVENTF_UNICODE,
    VK_CONTROL, VK_LCONTROL, VK_RCONTROL,
    VK_MENU, VK_LMENU, VK_RMENU,
    VK_SHIFT, VK_LSHIFT, VK_RSHIFT,
    VK_LWIN, VK_RWIN,
    VK_F1, VK_F2, VK_F3, VK_F4, VK_F5, VK_F6, VK_F7, VK_F8, VK_F9, VK_F10, VK_F11, VK_F12,
};

const CF_UNICODETEXT: u32 = 13;
const VK_V: VIRTUAL_KEY = VIRTUAL_KEY(0x56);

#[link(name = "kernel32")]
extern "system" {
    fn GlobalFree(hmem: *mut std::ffi::c_void) -> *mut std::ffi::c_void;
}

fn send_dummy_key() {
    unsafe {
        let down = INPUT {
            r#type: INPUT_KEYBOARD,
            Anonymous: INPUT_0 {
                ki: KEYBDINPUT {
                    wVk: VIRTUAL_KEY(0xE8),
                    wScan: 0,
                    dwFlags: Default::default(),
                    time: 0,
                    dwExtraInfo: 0,
                },
            },
        };
        let up = INPUT {
            r#type: INPUT_KEYBOARD,
            Anonymous: INPUT_0 {
                ki: KEYBDINPUT {
                    wVk: VIRTUAL_KEY(0xE8),
                    wScan: 0,
                    dwFlags: KEYEVENTF_KEYUP,
                    time: 0,
                    dwExtraInfo: 0,
                },
            },
        };
        let _ = SendInput(&[down, up], std::mem::size_of::<INPUT>() as i32);
    }
}

fn release_modifiers() {
    unsafe {
        let keys = [
            VK_CONTROL, VK_LCONTROL, VK_RCONTROL,
            VK_MENU, VK_LMENU, VK_RMENU,
            VK_SHIFT, VK_LSHIFT, VK_RSHIFT,
            VK_LWIN, VK_RWIN,
            VK_F1, VK_F2, VK_F3, VK_F4, VK_F5, VK_F6, VK_F7, VK_F8, VK_F9, VK_F10, VK_F11, VK_F12,
        ];

        // 1. Wait for physical release (up to 1.0 second)
        let start = std::time::Instant::now();
        while start.elapsed() < Duration::from_secs(1) {
            let mut still_down = false;
            for vk in keys {
                if (GetAsyncKeyState(vk.0 as i32) as u16 & 0x8000) != 0 {
                    still_down = true;
                    break;
                }
            }
            if !still_down {
                break;
            }
            thread::sleep(Duration::from_millis(10));
        }

        // 2. Determine which keys are logically down and release them
        let mut keys_to_release = Vec::new();
        for vk in keys {
            if (GetAsyncKeyState(vk.0 as i32) as u16 & 0x8000) != 0 {
                keys_to_release.push(vk);
            }
        }

        if keys_to_release.is_empty() {
            return;
        }

        // If Alt is in the list, send dummy key 0xE8 to prevent menu activation
        if keys_to_release.iter().any(|&vk| vk == VK_MENU || vk == VK_LMENU || vk == VK_RMENU) {
            send_dummy_key();
        }

        // Send KeyUp events for all keys to release
        let mut inputs = Vec::new();
        for vk in keys_to_release {
            inputs.push(INPUT {
                r#type: INPUT_KEYBOARD,
                Anonymous: INPUT_0 {
                    ki: KEYBDINPUT {
                        wVk: vk,
                        wScan: 0,
                        dwFlags: KEYEVENTF_KEYUP,
                        time: 0,
                        dwExtraInfo: 0,
                    },
                },
            });
        }
        let _ = SendInput(&inputs, std::mem::size_of::<INPUT>() as i32);
        thread::sleep(Duration::from_millis(50));
    }
}

fn open_clipboard_retry(max_attempts: usize, delay: Duration) -> bool {
    unsafe {
        for _ in 0..max_attempts {
            if OpenClipboard(HWND::default()).is_ok() {
                return true;
            }
            thread::sleep(delay);
        }
        false
    }
}

fn inject_via_clipboard(text: &str, delay: Duration) -> Result<(), String> {
    unsafe {
        // 1. Retrieve current clipboard content
        let mut old_content: Option<String> = None;
        if open_clipboard_retry(3, Duration::from_millis(50)) {
            if IsClipboardFormatAvailable(CF_UNICODETEXT).is_ok() {
                if let Ok(h_mem) = GetClipboardData(CF_UNICODETEXT) {
                    let h_global = HGLOBAL(h_mem.0);
                    let ptr = GlobalLock(h_global);
                    if !ptr.is_null() {
                        let mut len = 0;
                        let mut current = ptr as *const u16;
                        while *current != 0 {
                            len += 1;
                            current = current.add(1);
                        }
                        let slice = std::slice::from_raw_parts(ptr as *const u16, len);
                        if let Ok(s) = String::from_utf16(slice) {
                            old_content = Some(s);
                        }
                        let _ = GlobalUnlock(h_global);
                    }
                }
            }
            let _ = CloseClipboard();
        }

        // 2. Set new clipboard content
        let mut wide: Vec<u16> = text.encode_utf16().collect();
        wide.push(0);
        let byte_size = wide.len() * std::mem::size_of::<u16>();

        let h_mem = GlobalAlloc(GMEM_MOVEABLE, byte_size)
            .map_err(|e| format!("GlobalAlloc failed: {e}"))?;
        let ptr = GlobalLock(h_mem);
        if ptr.is_null() {
            let _ = GlobalFree(h_mem.0);
            return Err("GlobalLock failed".to_string());
        }
        copy_nonoverlapping(wide.as_ptr(), ptr as *mut u16, wide.len());
        let _ = GlobalUnlock(h_mem);

        if !open_clipboard_retry(3, Duration::from_millis(50)) {
            let _ = GlobalFree(h_mem.0);
            return Err("Failed to open clipboard for writing".to_string());
        }

        if let Err(e) = EmptyClipboard() {
            let _ = CloseClipboard();
            let _ = GlobalFree(h_mem.0);
            return Err(format!("EmptyClipboard failed: {e}"));
        }

        if let Err(e) = SetClipboardData(CF_UNICODETEXT, HANDLE(h_mem.0 as *mut _)) {
            let _ = CloseClipboard();
            let _ = GlobalFree(h_mem.0);
            return Err(format!("SetClipboardData failed: {e}"));
        }
        let _ = CloseClipboard();

        // 3. Sleep delay to let target window register clipboard change
        thread::sleep(delay);

        // 4. Send Ctrl+V sequence
        let ctrl_down = INPUT {
            r#type: INPUT_KEYBOARD,
            Anonymous: INPUT_0 {
                ki: KEYBDINPUT {
                    wVk: VK_CONTROL,
                    wScan: 0,
                    dwFlags: Default::default(),
                    time: 0,
                    dwExtraInfo: 0,
                },
            },
        };
        let v_down = INPUT {
            r#type: INPUT_KEYBOARD,
            Anonymous: INPUT_0 {
                ki: KEYBDINPUT {
                    wVk: VK_V,
                    wScan: 0,
                    dwFlags: Default::default(),
                    time: 0,
                    dwExtraInfo: 0,
                },
            },
        };
        let v_up = INPUT {
            r#type: INPUT_KEYBOARD,
            Anonymous: INPUT_0 {
                ki: KEYBDINPUT {
                    wVk: VK_V,
                    wScan: 0,
                    dwFlags: KEYEVENTF_KEYUP,
                    time: 0,
                    dwExtraInfo: 0,
                },
            },
        };
        let ctrl_up = INPUT {
            r#type: INPUT_KEYBOARD,
            Anonymous: INPUT_0 {
                ki: KEYBDINPUT {
                    wVk: VK_CONTROL,
                    wScan: 0,
                    dwFlags: KEYEVENTF_KEYUP,
                    time: 0,
                    dwExtraInfo: 0,
                },
            },
        };

        let _ = SendInput(&[ctrl_down], std::mem::size_of::<INPUT>() as i32);
        thread::sleep(Duration::from_millis(10));
        let _ = SendInput(&[v_down], std::mem::size_of::<INPUT>() as i32);
        thread::sleep(Duration::from_millis(50));
        let _ = SendInput(&[v_up], std::mem::size_of::<INPUT>() as i32);
        thread::sleep(Duration::from_millis(10));
        let _ = SendInput(&[ctrl_up], std::mem::size_of::<INPUT>() as i32);
        thread::sleep(Duration::from_millis(50));

        // 5. Spawn background thread to restore old clipboard content after 1 second
        if let Some(old) = old_content {
            thread::spawn(move || {
                thread::sleep(Duration::from_secs(1));
                let mut wide_old: Vec<u16> = old.encode_utf16().collect();
                wide_old.push(0);
                let size_old = wide_old.len() * std::mem::size_of::<u16>();

                if let Ok(h_mem_old) = GlobalAlloc(GMEM_MOVEABLE, size_old) {
                    let ptr_old = GlobalLock(h_mem_old);
                    if !ptr_old.is_null() {
                        copy_nonoverlapping(wide_old.as_ptr(), ptr_old as *mut u16, wide_old.len());
                        let _ = GlobalUnlock(h_mem_old);
                        if open_clipboard_retry(5, Duration::from_millis(50)) {
                            let _ = EmptyClipboard();
                            let _ = SetClipboardData(CF_UNICODETEXT, HANDLE(h_mem_old.0 as *mut _));
                            let _ = CloseClipboard();
                        } else {
                            let _ = GlobalFree(h_mem_old.0);
                        }
                    } else {
                        let _ = GlobalFree(h_mem_old.0);
                    }
                }
            });
        }

        Ok(())
    }
}

fn inject_via_sendinput(text: &str, char_delay_ms: u64) -> Result<(), String> {
    unsafe {
        for char in text.chars() {
            let mut wide_buf = [0u16; 2];
            let wide_chars = char.encode_utf16(&mut wide_buf);
            
            for &code in wide_chars.iter() {
                // key down
                let down = INPUT {
                    r#type: INPUT_KEYBOARD,
                    Anonymous: INPUT_0 {
                        ki: KEYBDINPUT {
                            wVk: Default::default(),
                            wScan: code,
                            dwFlags: KEYEVENTF_UNICODE,
                            time: 0,
                            dwExtraInfo: 0,
                        },
                    },
                };

                // key up
                let up = INPUT {
                    r#type: INPUT_KEYBOARD,
                    Anonymous: INPUT_0 {
                        ki: KEYBDINPUT {
                            wVk: Default::default(),
                            wScan: code,
                            dwFlags: KEYEVENTF_UNICODE | KEYEVENTF_KEYUP,
                            time: 0,
                            dwExtraInfo: 0,
                        },
                    },
                };

                // Send down and up together as a single atomic event packet
                let _ = SendInput(&[down, up], std::mem::size_of::<INPUT>() as i32);
                
                // Sleep only between characters to allow the target app's message loop to keep up
                thread::sleep(Duration::from_millis(char_delay_ms));
            }
        }
        Ok(())
    }
}

#[tauri::command]
pub async fn inject_text(
    text: String,
    method: Option<String>,
    delay_ms: Option<u64>,
) -> Result<(), String> {
    if text.is_empty() {
        return Ok(());
    }

    // Release modifier keys first to prevent key conflicts
    release_modifiers();

    let method_str = method.unwrap_or_else(|| "clipboard".to_string());
    let delay_val = delay_ms.unwrap_or(50);

    if method_str == "sendinput" {
        // Derive character delay: 10% of configured delay, min 5ms.
        // E.g., at 50ms delay, char delay is 5ms. If user scales delay to 150ms under load, char delay becomes 15ms.
        let char_delay = (delay_val / 10).max(5);
        inject_via_sendinput(&text, char_delay)
    } else {
        inject_via_clipboard(&text, Duration::from_millis(delay_val))
    }
}
