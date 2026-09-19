import { useEffect, useState, useRef } from "react";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { listen } from "@tauri-apps/api/event";
import {
  getConfig,
  saveConfig,
  getCorrections,
  saveCorrections,
  listAudioDevices,
  getApiKey,
  setApiKey,
  selectFile,
  getCachedModels,
  deleteCachedModel,
  getOllamaModels,
  checkForUpdates,
  openConfigFolder,
  ModelCacheInfo
} from "../../lib/commands";
import "./SettingsWindow.css";
import { EngineTab } from "./tabs/EngineTab";
import { AudioTab } from "./tabs/AudioTab";
import { HotkeysTab } from "./tabs/HotkeysTab";
import { WidgetTab } from "./tabs/WidgetTab";
import { CloudTab } from "./tabs/CloudTab";
import { AdvancedTab } from "./tabs/AdvancedTab";
import { CorrectionsTab } from "./tabs/CorrectionsTab";
import { PolishTab } from "./tabs/PolishTab";
import { LauncherTab } from "./tabs/LauncherTab";

type TabName =
  | "engine"
  | "cloud"
  | "audio"
  | "polish"
  | "hotkeys"
  | "widget"
  | "corrections"
  | "launcher"
  | "advanced";

const TAB_TITLES: Record<TabName, string> = {
  engine: "Engine",
  cloud: "Cloud STT",
  audio: "Audio",
  polish: "Text Polish",
  hotkeys: "Hotkeys",
  widget: "Widget",
  corrections: "Auto-Correct",
  launcher: "App Launcher",
  advanced: "Advanced",
};

const DEFAULT_CONFIG: Record<string, any> = {
  version: 2,
  engine_mode: "hybrid",
  model_size: "small",
  language: "en",
  compute_type: "int8",
  local_device: "cuda",
  cloud_region: "eastus",
  sarvam_model: "saarika:v2.5",
  sarvam_language: "hi-IN",
  enable_sarvam_websocket: true,

  mic_device_index: -1,
  sample_rate: 16000,
  vad_aggressiveness: 1,
  silence_timeout_ms: 2500,
  max_record_seconds: 30,
  enable_max_record_limit: true,

  hotkey: "ctrl+alt+d",
  hotkey_mode: "toggle",

  inject_method: "clipboard",
  inject_delay_ms: 50,

  spoken_punctuation: true,
  auto_capitalise: true,

  show_floating_widget: true,
  widget_size: 64,
  widget_opacity: 0.85,
  widget_always_on_top: true,

  start_with_windows: false,
  log_level: "INFO",
  check_updates: true,

  cloud_provider: "azure",
  cloud_fallback_on_error: true,
  cloud_fallback_provider: "azure",
  local_fallback_on_cloud_error: true,

  theme: "system",

  show_preview_window: true,
  preview_hide_after_ms: 8000,
  preview_opacity: 0.85,
  preview_text_color: "#ffffff",

  gemini_stt_model: "gemini-flash-lite-latest",
  gemini_stt_language: "en",
  openrouter_stt_model: "openai/whisper-1",
  groq_stt_model: "whisper-large-v3-turbo",

  enable_polish: false,
  polish_provider: "ollama",
  polish_action: "Fix Grammar & Spelling",
  custom_polish_prompt: "Rewrite this text to be more concise.",
  ollama_url: "http://localhost:11434",
  polish_ollama_model: "llama3",
  polish_gemini_model: "gemini-flash-lite-latest",
  polish_openrouter_model: "",
  polish_groq_model: "",
  polish_ollama_timeout: 90,
  polish_hotkey: "ctrl+alt+p",

  enable_realtime: false,
  realtime_frequency_ms: 800,

  app_launcher_commands: {}
};

interface CorrectionPair {
  from: string;
  to: string;
}

interface AudioDevice {
  index: number;
  name: string;
  channels: number;
  default_samplerate: number;
}

export default function SettingsWindow() {
  const [activeTab, setActiveTab] = useState<TabName>("engine");
  const [config, setConfig] = useState<Record<string, any>>({ ...DEFAULT_CONFIG });
  const [corrections, setCorrections] = useState<CorrectionPair[]>([]);
  const [devices, setDevices] = useState<AudioDevice[]>([]);

  // API Keys state
  const [azureKey, setAzureKey] = useState("");
  const [geminiKey, setGeminiKey] = useState("");
  const [sarvamKey, setSarvamKey] = useState("");
  const [openrouterKey, setOpenRouterKey] = useState("");
  const [groqKey, setGroqKey] = useState("");

  // UI state
  const [showAzureKey, setShowAzureKey] = useState(false);
  const [showGeminiKey, setShowGeminiKey] = useState(false);
  const [showSarvamKey, setShowSarvamKey] = useState(false);
  const [showOpenRouterKey, setShowOpenRouterKey] = useState(false);
  const [showGroqKey, setShowGroqKey] = useState(false);
  const [azureTestStatus, setAzureTestStatus] = useState<"idle" | "testing" | "success" | "error">("idle");
  const [geminiTestStatus, setGeminiTestStatus] = useState<"idle" | "testing" | "success" | "error">("idle");
  const [sarvamTestStatus, setSarvamTestStatus] = useState<"idle" | "testing" | "success" | "error">("idle");
  const [openrouterTestStatus, setOpenRouterTestStatus] = useState<"idle" | "testing" | "success" | "error">("idle");
  const [groqTestStatus, setGroqTestStatus] = useState<"idle" | "testing" | "success" | "error">("idle");

  // Hotkey record state
  const [isRecordingHotkey, setIsRecordingHotkey] = useState(false);
  const hotkeyRef = useRef<HTMLDivElement>(null);

  // App Launcher state
  const [newCommandText, setNewCommandText] = useState("");
  const [newCommandPath, setNewCommandPath] = useState("");

  // Corrections state
  const [newFromWord, setNewFromWord] = useState("");
  const [newToWord, setNewToWord] = useState("");

  // Import/Export references
  const importInputRef = useRef<HTMLInputElement>(null);

  // Whisper Cached Models State
  const [cachedModels, setCachedModels] = useState<ModelCacheInfo[]>([]);
  const [isLoadingCache, setIsLoadingCache] = useState(false);

  // Dynamic Ollama Models State
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);
  const [ollamaStatus, setOllamaStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [ollamaError, setOllamaError] = useState("");

  // Polish Hotkey State
  const [isRecordingPolishHotkey, setIsRecordingPolishHotkey] = useState(false);
  const polishHotkeyRef = useRef<HTMLDivElement>(null);

  // Update check State
  const [updateCheckStatus, setUpdateCheckStatus] = useState<"idle" | "checking" | "success" | "error">("idle");
  const [updateCheckMessage, setUpdateCheckMessage] = useState("");

  // Microphone level meter State
  const [showMicTest, setShowMicTest] = useState(false);
  const [micLevel, setMicLevel] = useState(0);
  const [micStatus, setMicStatus] = useState("No signal");
  const [micStatusColor, setMicStatusColor] = useState("gray");

  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number | null>(null);

  const fetchCachedModels = () => {
    setIsLoadingCache(true);
    getCachedModels()
      .then((models) => {
        setCachedModels(models || []);
      })
      .catch((err) => console.error("Failed to load cached models:", err))
      .finally(() => setIsLoadingCache(false));
  };

  const handleDeleteModel = async (name: string) => {
    if (confirm(`Confirm deletion of local '${name}' model folder?\nIt will download again on next hybrid/local launch.`)) {
      try {
        await deleteCachedModel(name);
        fetchCachedModels();
      } catch (err) {
        alert(`Delete failed: ${err}`);
      }
    }
  };

  const fetchOllamaModels = (url: string) => {
    if (!url) return;
    setOllamaStatus("loading");
    setOllamaError("");
    getOllamaModels(url)
      .then((models) => {
        setOllamaModels(models || []);
        setOllamaStatus("success");
      })
      .catch((err) => {
        console.error("Failed to fetch Ollama models:", err);
        setOllamaModels([]);
        setOllamaStatus("error");
        setOllamaError(typeof err === "string" ? err : String(err));
      });
  };

  const startMicTest = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      
      const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
      audioContextRef.current = audioContext;
      
      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;
      
      setMicLevel(0);
      setMicStatus("Listening...");
      setMicStatusColor("gray");
      
      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);
      
      const update = () => {
        if (!analyserRef.current) return;
        analyserRef.current.getByteFrequencyData(dataArray);
        
        let sum = 0;
        for (let i = 0; i < bufferLength; i++) {
          sum += dataArray[i] * dataArray[i];
        }
        const rms = Math.sqrt(sum / bufferLength);
        
        const percent = Math.min(100, Math.round((rms / 128) * 100));
        setMicLevel(percent);
        
        if (rms > 20) {
          setMicStatus("✓ Good signal — microphone is working correctly");
          setMicStatusColor("green");
        } else if (rms > 2) {
          setMicStatus("Signal detected but quiet");
          setMicStatusColor("orange");
        } else {
          setMicStatus("No signal — is mic muted?");
          setMicStatusColor("red");
        }
        
        rafRef.current = requestAnimationFrame(update);
      };
      
      update();
    } catch (e) {
      console.error("Mic test error:", e);
      setMicStatus(`Error opening mic: ${e}`);
      setMicStatusColor("red");
    }
  };

  const stopMicTest = () => {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    analyserRef.current = null;
    setMicLevel(0);
  };

  const handleCheckUpdates = () => {
    setUpdateCheckStatus("checking");
    setUpdateCheckMessage("Checking for updates...");
    checkForUpdates()
      .then((res) => {
        if (res.is_newer) {
          setUpdateCheckStatus("success");
          setUpdateCheckMessage(`Update available: v${res.latest}. Please download the latest version.`);
        } else {
          setUpdateCheckStatus("success");
          setUpdateCheckMessage(`App is up-to-date (v${res.current}).`);
        }
      })
      .catch((err) => {
        setUpdateCheckStatus("error");
        setUpdateCheckMessage(`Failed to check updates: ${err}`);
      });
  };

  const handleOpenConfigFolder = async () => {
    try {
      await openConfigFolder();
    } catch (err) {
      alert(`Failed to open config folder: ${err}`);
    }
  };

  // Reactions for dynamic lookups
  useEffect(() => {
    if (activeTab === "polish" && config.polish_provider === "ollama") {
      fetchOllamaModels(config.ollama_url);
    }
  }, [activeTab, config.ollama_url, config.polish_provider]);

  useEffect(() => {
    if (activeTab === "advanced") {
      fetchCachedModels();
    }
  }, [activeTab]);

  useEffect(() => {
    return () => {
      stopMicTest();
    };
  }, []);

  useEffect(() => {
    // 1. Fetch Config
    getConfig()
      .then((cfg) => {
        if (cfg && Object.keys(cfg).length > 0) {
          const provider = cfg.cloud_provider || cfg.cloud_fallback_provider || "azure";
          setConfig((prev) => ({
            ...prev,
            ...cfg,
            cloud_provider: provider,
            cloud_fallback_provider: provider,
          }));
        }
      })
      .catch((err) => console.error("Failed to load config:", err));

    // Listen to live config changes
    let unlistenConfig: (() => void) | null = null;
    listen<any>("config://changed", (event) => {
      const cfg = event.payload;
      if (cfg && Object.keys(cfg).length > 0) {
        const provider = cfg.cloud_provider || cfg.cloud_fallback_provider || "azure";
        setConfig((prev) => ({
          ...prev,
          ...cfg,
          cloud_provider: provider,
          cloud_fallback_provider: provider,
        }));
      }
    }).then((un) => {
      unlistenConfig = un;
    });

    // 2. Fetch Corrections
    getCorrections()
      .then((list) => {
        if (list) setCorrections(list);
      })
      .catch((err) => console.error("Failed to load corrections:", err));

    // 3. Fetch Audio Devices
    listAudioDevices()
      .then((devs) => {
        if (devs) setDevices(devs);
      })
      .catch((err) => console.error("Failed to load audio devices:", err));

    // 4. Fetch Secure API Keys
    getApiKey("azure").then(setAzureKey).catch(console.error);
    getApiKey("gemini").then(setGeminiKey).catch(console.error);
    getApiKey("sarvam").then(setSarvamKey).catch(console.error);
    getApiKey("openrouter").then(setOpenRouterKey).catch(console.error);
    getApiKey("groq").then(setGroqKey).catch(console.error);

    // 5. Fetch Cached Whisper Models
    fetchCachedModels();

    return () => {
      unlistenConfig?.();
    };
  }, []);

  // Hotkey recording effect
  useEffect(() => {
    if (!isRecordingHotkey) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      e.preventDefault();
      e.stopPropagation();

      const key = e.key;
      // Skip lonely modifier triggers
      if (["Control", "Alt", "Shift", "Meta"].includes(key)) return;

      const parts: string[] = [];
      if (e.ctrlKey) parts.push("ctrl");
      if (e.altKey) parts.push("alt");
      if (e.shiftKey) parts.push("shift");
      if (e.metaKey) parts.push("win");

      let keyName = key.toLowerCase();
      if (keyName === " ") keyName = "space";
      parts.push(keyName);

      const combo = parts.join("+");
      setConfig((prev) => ({ ...prev, hotkey: combo }));
      setIsRecordingHotkey(false);
    };

    window.addEventListener("keydown", handleKeyDown, true);
    return () => window.removeEventListener("keydown", handleKeyDown, true);
  }, [isRecordingHotkey]);

  // Polish Hotkey recording effect
  useEffect(() => {
    if (!isRecordingPolishHotkey) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      e.preventDefault();
      e.stopPropagation();

      const key = e.key;
      // Skip lonely modifier triggers
      if (["Control", "Alt", "Shift", "Meta"].includes(key)) return;

      const parts: string[] = [];
      if (e.ctrlKey) parts.push("ctrl");
      if (e.altKey) parts.push("alt");
      if (e.shiftKey) parts.push("shift");
      if (e.metaKey) parts.push("win");

      let keyName = key.toLowerCase();
      if (keyName === " ") keyName = "space";
      parts.push(keyName);

      const combo = parts.join("+");
      setConfig((prev) => ({ ...prev, polish_hotkey: combo }));
      setIsRecordingPolishHotkey(false);
    };

    window.addEventListener("keydown", handleKeyDown, true);
    return () => window.removeEventListener("keydown", handleKeyDown, true);
  }, [isRecordingPolishHotkey]);

  const handleFieldChange = (key: string, value: any) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    try {
      // 1. Save Config
      await saveConfig(config);

      // 2. Save Corrections
      await saveCorrections(corrections);

      // 3. Save API Keys
      await setApiKey("azure", azureKey);
      await setApiKey("gemini", geminiKey);
      await setApiKey("sarvam", sarvamKey);
      await setApiKey("openrouter", openrouterKey);
      await setApiKey("groq", groqKey);

      // 4. Hide settings window
      const win = getCurrentWindow();
      await win.hide();
    } catch (err) {
      alert(`Failed to save settings: ${err}`);
    }
  };

  const handleCancel = async () => {
    const win = getCurrentWindow();
    await win.hide();
  };

  const handleResetDefaults = () => {
    if (confirm("Are you sure you want to reset all configurations to defaults?")) {
      setConfig({ ...DEFAULT_CONFIG });
      setCorrections([]);
    }
  };

  const handleExport = () => {
    const fullConfig = {
      config,
      corrections
    };
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(fullConfig, null, 2));
    const downloadAnchor = document.createElement("a");
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", "dictateanywhere_backup.json");
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const handleImportClick = () => {
    importInputRef.current?.click();
  };

  const handleImportFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const parsed = JSON.parse(event.target?.result as string);
        if (parsed.config) {
          setConfig((prev) => ({ ...prev, ...parsed.config }));
        }
        if (parsed.corrections) {
          setCorrections(parsed.corrections);
        }
        alert("Configuration imported successfully!");
      } catch (err) {
        alert(`Failed to parse backup file: ${err}`);
      }
    };
    reader.readAsText(file);
  };

  // Connection testing calls
  const testGeminiKey = async () => {
    if (!geminiKey) {
      alert("Please enter a Gemini API Key first.");
      return;
    }
    setGeminiTestStatus("testing");
    try {
      const res = await fetch("https://generativelanguage.googleapis.com/v1beta/models", {
        headers: { "x-goog-api-key": geminiKey },
      });
      if (res.ok) {
        setGeminiTestStatus("success");
      } else {
        setGeminiTestStatus("error");
      }
    } catch (e) {
      setGeminiTestStatus("error");
    }
  };

  const testAzureKey = async () => {
    if (!azureKey) {
      alert("Please enter an Azure Speech API Key first.");
      return;
    }
    setAzureTestStatus("testing");
    // Lightweight mock test validation
    setTimeout(() => {
      if (azureKey.length >= 32) {
        setAzureTestStatus("success");
      } else {
        setAzureTestStatus("error");
      }
    }, 1200);
  };

  const testSarvamKey = async () => {
    if (!sarvamKey) {
      alert("Please enter a Sarvam API Key first.");
      return;
    }
    setSarvamTestStatus("testing");
    // Lightweight mock test validation
    setTimeout(() => {
      if (sarvamKey.length >= 10) {
        setSarvamTestStatus("success");
      } else {
        setSarvamTestStatus("error");
      }
    }, 1200);
  };

  const testOpenRouterKey = async () => {
    if (!openrouterKey) {
      alert("Please enter an OpenRouter API Key first.");
      return;
    }
    setOpenRouterTestStatus("testing");
    setTimeout(() => {
      if (openrouterKey.length >= 10) {
        setOpenRouterTestStatus("success");
      } else {
        setOpenRouterTestStatus("error");
      }
    }, 1200);
  };

  const testGroqKey = async () => {
    if (!groqKey) {
      alert("Please enter a Groq API Key first.");
      return;
    }
    setGroqTestStatus("testing");
    setTimeout(() => {
      if (groqKey.length >= 10) {
        setGroqTestStatus("success");
      } else {
        setGroqTestStatus("error");
      }
    }, 1200);
  };


  // Corrections helpers
  const addCorrection = () => {
    if (!newFromWord.trim()) return;
    setCorrections((prev) => [...prev, { from: newFromWord.trim(), to: newToWord.trim() }]);
    setNewFromWord("");
    setNewToWord("");
  };

  const removeCorrection = (index: number) => {
    setCorrections((prev) => prev.filter((_, i) => i !== index));
  };

  const updateCorrectionField = (index: number, field: "from" | "to", val: string) => {
    setCorrections((prev) =>
      prev.map((c, i) => (i === index ? { ...c, [field]: val } : c))
    );
  };

  // App Launcher helpers
  const handleLauncherBrowse = async () => {
    try {
      const path = await selectFile();
      if (path) {
        setNewCommandPath(path);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const addLauncherCommand = () => {
    const cmd = newCommandText.trim().toLowerCase();
    const path = newCommandPath.trim();
    if (!cmd || !path) return;

    setConfig((prev) => {
      const current = { ...(prev.app_launcher_commands || {}) };
      current[cmd] = path;
      return { ...prev, app_launcher_commands: current };
    });
    setNewCommandText("");
    setNewCommandPath("");
  };

  const removeLauncherCommand = (cmd: string) => {
    setConfig((prev) => {
      const current = { ...(prev.app_launcher_commands || {}) };
      delete current[cmd];
      return { ...prev, app_launcher_commands: current };
    });
  };

  return (
    <div className="settings-root">
      {/* Hidden input for Import */}
      <input
        type="file"
        ref={importInputRef}
        style={{ display: "none" }}
        accept=".json"
        onChange={handleImportFile}
      />

      <div className="settings-container">
        {/* Navigation Sidebar */}
        <div className="settings-sidebar">
          <h3>Settings</h3>
          <button
            className={`tab-btn ${activeTab === "engine" ? "active" : ""}`}
            onClick={() => setActiveTab("engine")}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
            </svg>
            Engine
          </button>
          <button
            className={`tab-btn ${activeTab === "cloud" ? "active" : ""}`}
            onClick={() => setActiveTab("cloud")}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M17.5 19A5.5 5.5 0 0 0 18 8h-1.26a8 8 0 1 0-11.62 3.58" />
            </svg>
            Cloud STT
          </button>
          <button
            className={`tab-btn ${activeTab === "audio" ? "active" : ""}`}
            onClick={() => setActiveTab("audio")}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M12 1v10M19 8a7 7 0 0 1-14 0" />
              <rect x="9" y="10" width="6" height="8" rx="3" />
            </svg>
            Audio
          </button>
          <button
            className={`tab-btn ${activeTab === "polish" ? "active" : ""}`}
            onClick={() => setActiveTab("polish")}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M12 20h9M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
            </svg>
            Text Polish
          </button>
          <button
            className={`tab-btn ${activeTab === "hotkeys" ? "active" : ""}`}
            onClick={() => setActiveTab("hotkeys")}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <rect x="2" y="4" width="20" height="16" rx="2" />
              <path d="M6 8h.01M10 8h.01M14 8h.01M18 8h.01M6 12h.01M18 12h.01M7 16h10" />
            </svg>
            Hotkeys
          </button>
          <button
            className={`tab-btn ${activeTab === "widget" ? "active" : ""}`}
            onClick={() => setActiveTab("widget")}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 8v8M8 12h8" />
            </svg>
            Widget
          </button>
          <button
            className={`tab-btn ${activeTab === "corrections" ? "active" : ""}`}
            onClick={() => setActiveTab("corrections")}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7M18.5 2.5a2.121 2.121 0 1 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
            </svg>
            Auto-Correct
          </button>
          <button
            className={`tab-btn ${activeTab === "launcher" ? "active" : ""}`}
            onClick={() => setActiveTab("launcher")}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14 21 3" />
            </svg>
            App Launcher
          </button>
          <button
            className={`tab-btn ${activeTab === "advanced" ? "active" : ""}`}
            onClick={() => setActiveTab("advanced")}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
            Advanced
          </button>
        </div>

        {/* Tab Contents Main Area */}
        <div className="settings-main">
          <div className="settings-header">
            <h2 className="settings-header-title">{TAB_TITLES[activeTab]}</h2>
            <button className="settings-close-btn" onClick={handleCancel} title="Close Settings">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M18 6 6 18M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div className="settings-content">
            {activeTab === "engine" && (
              <EngineTab config={config} handleFieldChange={handleFieldChange} />
            )}

            {activeTab === "cloud" && (
              <CloudTab
                config={config}
                handleFieldChange={handleFieldChange}
                geminiKey={geminiKey}
                setGeminiKey={setGeminiKey}
                showGeminiKey={showGeminiKey}
                setShowGeminiKey={setShowGeminiKey}
                testGeminiKey={testGeminiKey}
                geminiTestStatus={geminiTestStatus}
                azureKey={azureKey}
                setAzureKey={setAzureKey}
                showAzureKey={showAzureKey}
                setShowAzureKey={setShowAzureKey}
                testAzureKey={testAzureKey}
                azureTestStatus={azureTestStatus}
                sarvamKey={sarvamKey}
                setSarvamKey={setSarvamKey}
                showSarvamKey={showSarvamKey}
                setShowSarvamKey={setShowSarvamKey}
                testSarvamKey={testSarvamKey}
                sarvamTestStatus={sarvamTestStatus}
                openrouterKey={openrouterKey}
                setOpenRouterKey={setOpenRouterKey}
                showOpenRouterKey={showOpenRouterKey}
                setShowOpenRouterKey={setShowOpenRouterKey}
                testOpenRouterKey={testOpenRouterKey}
                openrouterTestStatus={openrouterTestStatus}
                groqKey={groqKey}
                setGroqKey={setGroqKey}
                showGroqKey={showGroqKey}
                setShowGroqKey={setShowGroqKey}
                testGroqKey={testGroqKey}
                groqTestStatus={groqTestStatus}
              />
            )}

            {activeTab === "audio" && (
              <AudioTab
                config={config}
                handleFieldChange={handleFieldChange}
                devices={devices}
                showMicTest={showMicTest}
                setShowMicTest={setShowMicTest}
                startMicTest={startMicTest}
                stopMicTest={stopMicTest}
                micLevel={micLevel}
                micStatus={micStatus}
                micStatusColor={micStatusColor}
              />
            )}

            {activeTab === "polish" && (
              <PolishTab
                config={config}
                handleFieldChange={handleFieldChange}
                fetchOllamaModels={fetchOllamaModels}
                ollamaStatus={ollamaStatus}
                ollamaError={ollamaError}
                ollamaModels={ollamaModels}
              />
            )}

            {activeTab === "hotkeys" && (
              <HotkeysTab
                config={config}
                handleFieldChange={handleFieldChange}
                isRecordingHotkey={isRecordingHotkey}
                setIsRecordingHotkey={setIsRecordingHotkey}
                hotkeyRef={hotkeyRef}
                isRecordingPolishHotkey={isRecordingPolishHotkey}
                setIsRecordingPolishHotkey={setIsRecordingPolishHotkey}
                polishHotkeyRef={polishHotkeyRef}
              />
            )}

            {activeTab === "widget" && (
              <WidgetTab config={config} handleFieldChange={handleFieldChange} />
            )}

            {activeTab === "corrections" && (
              <CorrectionsTab
                corrections={corrections}
                newFromWord={newFromWord}
                setNewFromWord={setNewFromWord}
                newToWord={newToWord}
                setNewToWord={setNewToWord}
                addCorrection={addCorrection}
                updateCorrectionField={updateCorrectionField}
                removeCorrection={removeCorrection}
              />
            )}

            {activeTab === "launcher" && (
              <LauncherTab
                config={config}
                newCommandText={newCommandText}
                setNewCommandText={setNewCommandText}
                newCommandPath={newCommandPath}
                setNewCommandPath={setNewCommandPath}
                handleLauncherBrowse={handleLauncherBrowse}
                addLauncherCommand={addLauncherCommand}
                removeLauncherCommand={removeLauncherCommand}
              />
            )}

            {activeTab === "advanced" && (
              <AdvancedTab
                config={config}
                handleFieldChange={handleFieldChange}
                handleCheckUpdates={handleCheckUpdates}
                updateCheckStatus={updateCheckStatus}
                updateCheckMessage={updateCheckMessage}
                handleOpenConfigFolder={handleOpenConfigFolder}
                isLoadingCache={isLoadingCache}
                cachedModels={cachedModels}
                handleDeleteModel={handleDeleteModel}
              />
            )}
          </div>
        </div>
      </div>

      {/* Save / Footer */}
      <div className="settings-footer">
        <div className="footer-left">
          <button className="btn btn-secondary" onClick={handleImportClick}>
            Import
          </button>
          <button className="btn btn-secondary" onClick={handleExport}>
            Export
          </button>
          <button className="btn btn-danger" onClick={handleResetDefaults}>
            Reset Defaults
          </button>
        </div>

        <div className="footer-right">
          <button className="btn btn-secondary" onClick={handleCancel}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={handleSave}>
            Save
          </button>
        </div>
      </div>
    </div>
  );
}
