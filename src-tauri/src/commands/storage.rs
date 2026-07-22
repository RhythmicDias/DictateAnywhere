// src-tauri/src/commands/storage.rs
//! Secure storage command handlers using the keyring crate (Windows Credential Manager).
//! Maintains username compatibility with Python keyring to preserve existing credentials.

use keyring::Entry;

const SERVICE_NAME: &str = "DictateAnywhere";

fn map_service_name(service: &str) -> &str {
    match service {
        "azure" => "azure_speech_api_key",
        "sarvam" => "sarvam_api_key",
        "gemini" => "gemini_api_key",
        "openrouter" => "openrouter_api_key",
        "groq" => "groq_api_key",
        other => other,
    }
}

#[tauri::command]
pub fn get_api_key(service: String) -> Result<Option<String>, String> {
    let credential_id = map_service_name(&service);
    let entry = Entry::new(SERVICE_NAME, credential_id).map_err(|e| e.to_string())?;
    match entry.get_password() {
        Ok(pass) => Ok(Some(pass)),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(e) => Err(e.to_string()),
    }
}

#[tauri::command]
pub fn set_api_key(service: String, key: String) -> Result<(), String> {
    let credential_id = map_service_name(&service);
    let entry = Entry::new(SERVICE_NAME, credential_id).map_err(|e| e.to_string())?;
    if key.trim().is_empty() {
        match entry.delete_password() {
            Ok(_) | Err(keyring::Error::NoEntry) => Ok(()),
            Err(e) => Err(e.to_string()),
        }
    } else {
        entry.set_password(&key).map_err(|e| e.to_string())?;
        Ok(())
    }
}
