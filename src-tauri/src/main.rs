// src-tauri/src/main.rs
// Prevents additional console window on Windows in release mode.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    std::panic::set_hook(Box::new(|info| {
        let appdata = std::env::var("APPDATA").unwrap_or_else(|_| ".".to_string());
        let log_path = std::path::Path::new(&appdata).join("DictateAnywhere").join("crash.log");
        let msg = format!("Panic: {:?}\nBacktrace: {:?}", info, std::backtrace::Backtrace::capture());
        eprintln!("{}", msg);
        let _ = std::fs::write(log_path, msg);
    }));

    dictateanywhere_lib::run();
}
