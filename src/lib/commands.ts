import { invoke } from "@tauri-apps/api/core";

/** Return the full config JSON from %APPDATA%\DictateAnywhere\config.json */
export async function getConfig(): Promise<Record<string, unknown>> {
  return invoke<Record<string, unknown>>("get_config");
}

/** Atomically save the config JSON. */
export async function saveConfig(config: Record<string, unknown>): Promise<void> {
  return invoke("save_config", { config });
}

/** Register a global hotkey. mode: "toggle" | "push_to_talk" */
export async function registerHotkey(hotkey: string, mode: string): Promise<void> {
  return invoke("register_hotkey", { hotkey, mode });
}

/** Unregister a global hotkey. */
export async function unregisterHotkey(hotkey: string): Promise<void> {
  return invoke("unregister_hotkey", { hotkey });
}

/** Get list of corrections from corrections.json */
export async function getCorrections(): Promise<Array<{ from: string; to: string }>> {
  return invoke<Array<{ from: string; to: string }>>("get_corrections");
}

/** Save list of corrections to corrections.json */
export async function saveCorrections(corrections: Array<{ from: string; to: string }>): Promise<void> {
  return invoke("save_corrections", { corrections });
}

/** List all input audio devices from sounddevice */
export async function listAudioDevices(): Promise<Array<{ index: number; name: string; channels: number; default_samplerate: number }>> {
  return invoke<Array<{ index: number; name: string; channels: number; default_samplerate: number }>>("list_audio_devices");
}

/** Get API key for a cloud speech service */
export async function getApiKey(service: string): Promise<string> {
  const key = await invoke<string | null>("get_api_key", { service });
  return key ?? "";
}

/** Set API key for a cloud speech service */
export async function setApiKey(service: string, key: string): Promise<void> {
  return invoke("set_api_key", { service, key });
}

/** Open native open file dialog and return path */
export async function selectFile(): Promise<string | null> {
  return invoke<string | null>("select_file");
}

export interface ModelCacheInfo {
  name: string;
  size_mb: number;
}

export interface UpdateCheckResult {
  latest: string;
  url: string;
  is_newer: boolean;
  current: string;
}

export async function getCachedModels(): Promise<ModelCacheInfo[]> {
  return invoke<ModelCacheInfo[]>("get_cached_models");
}

export async function deleteCachedModel(name: string): Promise<void> {
  return invoke("delete_cached_model", { name });
}

export async function getOllamaModels(url: string): Promise<string[]> {
  return invoke<string[]>("get_ollama_models", { url });
}

export async function checkForUpdates(): Promise<UpdateCheckResult> {
  return invoke<UpdateCheckResult>("check_for_updates");
}

export async function openConfigFolder(): Promise<void> {
  return invoke("open_config_folder");
}

/** Export text to a file chosen by the user using a native file dialogue. */
export async function exportTextFile(text: string, defaultFilename: string): Promise<string | null> {
  return invoke<string | null>("export_text_file", { text, defaultFilename });
}
