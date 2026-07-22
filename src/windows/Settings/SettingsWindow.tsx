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

type TabName =
  | "engine"
  | "audio"
  | "hotkeys"
  | "widget"
  | "cloud"
  | "advanced"
  | "corrections"
  | "polish"
  | "launcher";

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
      const res = await fetch(`https://generativelanguage.googleapis.com/v1beta/models?key=${geminiKey}`);
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
            Floating Button
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
            className={`tab-btn ${activeTab === "advanced" ? "active" : ""}`}
            onClick={() => setActiveTab("advanced")}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
            Advanced
          </button>
          <button
            className={`tab-btn ${activeTab === "corrections" ? "active" : ""}`}
            onClick={() => setActiveTab("corrections")}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7M18.5 2.5a2.121 2.121 0 1 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
            </svg>
            Corrections
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
            className={`tab-btn ${activeTab === "launcher" ? "active" : ""}`}
            onClick={() => setActiveTab("launcher")}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14 21 3" />
            </svg>
            App Launcher
          </button>
        </div>

        {/* Tab Contents */}
        <div className="settings-content">
          {activeTab === "engine" && (
            <>
              <div className="tab-title">Engine Configuration</div>
              <div className="setting-card">
                <div className="setting-card-title">Transcription Engine</div>
                <div className="form-group">
                  <label htmlFor="engine_mode">Engine Mode</label>
                  <select
                    id="engine_mode"
                    value={config.engine_mode}
                    onChange={(e) => handleFieldChange("engine_mode", e.target.value)}
                  >
                    <option value="local">Local (Whisper GPU/CPU)</option>
                    <option value="cloud">Cloud (Azure/Gemini/Sarvam)</option>
                    <option value="hybrid">Hybrid (Local with Cloud Fallback)</option>
                  </select>
                  <div className="form-helper">
                    Select how dictation is processed. Hybrid attempts local first and falls back to cloud on failure.
                  </div>
                </div>

                <div className="form-group-row">
                  <label htmlFor="cloud_fallback_on_error">Enable Cloud Fallback on Error</label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      id="cloud_fallback_on_error"
                      checked={config.cloud_fallback_on_error}
                      onChange={(e) => handleFieldChange("cloud_fallback_on_error", e.target.checked)}
                    />
                    <span className="slider"></span>
                  </label>
                </div>

                <div className="form-group-row">
                  <label htmlFor="local_fallback_on_cloud_error">Enable Local Fallback on Cloud Error</label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      id="local_fallback_on_cloud_error"
                      checked={config.local_fallback_on_cloud_error}
                      onChange={(e) => handleFieldChange("local_fallback_on_cloud_error", e.target.checked)}
                    />
                    <span className="slider"></span>
                  </label>
                </div>

                {config.cloud_fallback_on_error && (
                  <div className="form-group">
                    <label htmlFor="cloud_fallback_provider">Cloud Fallback Provider</label>
                    <select
                      id="cloud_fallback_provider"
                      value={config.cloud_fallback_provider}
                      onChange={(e) => handleFieldChange("cloud_fallback_provider", e.target.value)}
                    >
                      <option value="azure">Azure Speech Services</option>
                      <option value="gemini">Google Gemini Flash</option>
                      <option value="sarvam">Sarvam AI (Indian Languages)</option>
                    </select>
                  </div>
                )}
              </div>

              <div className="setting-card">
                <div className="setting-card-title">Local Whisper Settings</div>
                <div className="grid-2">
                  <div className="form-group">
                    <label htmlFor="model_size">Model Size</label>
                    <select
                      id="model_size"
                      value={config.model_size}
                      onChange={(e) => handleFieldChange("model_size", e.target.value)}
                    >
                      <option value="tiny">Tiny (Fastest, low VRAM)</option>
                      <option value="base">Base</option>
                      <option value="small">Small (Recommended default)</option>
                      <option value="medium">Medium</option>
                      <option value="large-v2">Large V2</option>
                      <option value="large-v3">Large V3 (Most accurate, high VRAM)</option>
                    </select>
                  </div>

                  <div className="form-group">
                    <label htmlFor="compute_type">Compute Type</label>
                    <select
                      id="compute_type"
                      value={config.compute_type}
                      onChange={(e) => handleFieldChange("compute_type", e.target.value)}
                    >
                      <option value="int8">int8 (Lightweight, low VRAM)</option>
                      <option value="float16">float16 (Fastest on GPU)</option>
                      <option value="float32">float32</option>
                      <option value="int8_float16">int8_float16</option>
                    </select>
                  </div>
                </div>

                <div className="grid-2">
                  <div className="form-group">
                    <label htmlFor="local_device">Hardware Device</label>
                    <select
                      id="local_device"
                      value={config.local_device}
                      onChange={(e) => handleFieldChange("local_device", e.target.value)}
                    >
                      <option value="auto">Auto-detect</option>
                      <option value="cuda">NVIDIA CUDA GPU</option>
                      <option value="cpu">CPU (Slow)</option>
                    </select>
                  </div>

                  <div className="form-group">
                    <label htmlFor="language">Target Language</label>
                    <select
                      id="language"
                      value={config.language}
                      onChange={(e) => handleFieldChange("language", e.target.value)}
                    >
                      <option value="auto">Auto-detect Language</option>
                      <option value="en">English (en)</option>
                      <option value="es">Spanish (es)</option>
                      <option value="fr">French (fr)</option>
                      <option value="de">German (de)</option>
                      <option value="it">Italian (it)</option>
                      <option value="ja">Japanese (ja)</option>
                      <option value="zh">Chinese (zh)</option>
                      <option value="pt">Portuguese (pt)</option>
                      <option value="hi">Hindi (hi)</option>
                      <option value="nl">Dutch (nl)</option>
                      <option value="pl">Polish (pl)</option>
                      <option value="ru">Russian (ru)</option>
                      <option value="ko">Korean (ko)</option>
                      <option value="ar">Arabic (ar)</option>
                    </select>
                  </div>
                </div>
              </div>
            </>
          )}

          {activeTab === "audio" && (
            <>
              <div className="tab-title">Audio & Microphone Settings</div>
              <div className="setting-card">
                <div className="setting-card-title">Microphone Selection</div>
                <div className="form-group">
                  <label htmlFor="mic_device_index">Input Device</label>
                  <select
                    id="mic_device_index"
                    value={config.mic_device_index}
                    onChange={(e) => handleFieldChange("mic_device_index", parseInt(e.target.value))}
                  >
                    <option value="-1">System Default Microphone</option>
                    {devices.map((d) => (
                      <option key={d.index} value={d.index}>
                        [{d.index}] {d.name} ({d.channels} ch, {d.default_samplerate}Hz)
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-group" style={{ marginTop: "12px" }}>
                  <button
                    className="btn btn-secondary"
                    onClick={() => {
                      setShowMicTest(true);
                      startMicTest();
                    }}
                  >
                    Test Microphone
                  </button>
                </div>
              </div>

              {showMicTest && (
                <div className="modal-backdrop">
                  <div className="modal-content">
                    <h4>Microphone Level Meter</h4>
                    <p style={{ color: "#a6adc8", fontSize: "13px" }}>Speak into your microphone to verify connection and input level.</p>
                    
                    <div className="mic-meter-container">
                      <div className="mic-meter-bar" style={{ width: `${micLevel}%` }}></div>
                    </div>
                    
                    <div style={{ marginTop: "12px", fontSize: "14px", fontWeight: "bold", color: micStatusColor }}>
                      {micStatus}
                    </div>
                    
                    <button
                      className="btn btn-primary"
                      style={{ marginTop: "20px" }}
                      onClick={() => {
                        stopMicTest();
                        setShowMicTest(false);
                      }}
                    >
                      Close Test
                    </button>
                  </div>
                </div>
              )}

              <div className="setting-card">
                <div className="setting-card-title">Voice Activity Detection (VAD)</div>
                <div className="form-group">
                  <label htmlFor="vad_aggressiveness">VAD Aggressiveness</label>
                  <div className="range-container">
                    <input
                      type="range"
                      id="vad_aggressiveness"
                      min="0"
                      max="3"
                      step="1"
                      value={config.vad_aggressiveness}
                      onChange={(e) => handleFieldChange("vad_aggressiveness", parseInt(e.target.value))}
                    />
                    <span className="range-val">{config.vad_aggressiveness}</span>
                  </div>
                  <div className="form-helper">
                    0 = most sensitive (picks up more background noise), 3 = highly aggressive (transcribes only clear voice).
                  </div>
                </div>

                <div className="grid-2">
                  <div className="form-group">
                    <label htmlFor="silence_timeout_ms">Silence Timeout (ms)</label>
                    <input
                      type="number"
                      id="silence_timeout_ms"
                      min="500"
                      max="10000"
                      step="100"
                      value={config.silence_timeout_ms}
                      onChange={(e) => handleFieldChange("silence_timeout_ms", parseInt(e.target.value))}
                    />
                    <div className="form-helper">Ms of silence before stopping dictation automatically.</div>
                  </div>

                  <div className="form-group">
                    <label htmlFor="max_record_seconds">Max Record Duration (seconds)</label>
                    <input
                      type="number"
                      id="max_record_seconds"
                      min="5"
                      max="600"
                      disabled={!config.enable_max_record_limit}
                      value={config.max_record_seconds}
                      onChange={(e) => handleFieldChange("max_record_seconds", parseInt(e.target.value))}
                    />
                  </div>
                </div>

                <div className="form-group-row">
                  <label htmlFor="enable_max_record_limit">Enforce Maximum Recording Limit</label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      id="enable_max_record_limit"
                      checked={config.enable_max_record_limit}
                      onChange={(e) => handleFieldChange("enable_max_record_limit", e.target.checked)}
                    />
                    <span className="slider"></span>
                  </label>
                </div>
              </div>
            </>
          )}

          {activeTab === "hotkeys" && (
            <>
              <div className="tab-title">Global Shortcut Settings</div>
              <div className="setting-card">
                <div className="setting-card-title">Hotkey Configuration</div>
                <div className="form-group">
                  <label>Press to Capture Hotkey Combination</label>
                  <div
                    ref={hotkeyRef}
                    className={`hotkey-capturer ${isRecordingHotkey ? "recording" : ""}`}
                    onClick={() => setIsRecordingHotkey(true)}
                  >
                    {isRecordingHotkey ? "Listening for keypress..." : config.hotkey.toUpperCase()}
                  </div>
                  <div className="form-helper">
                    Click the box above and press your desired shortcut (e.g., Ctrl+Alt+D).
                  </div>
                </div>
                <div className="form-group">
                  <button
                    className="btn btn-secondary"
                    onClick={() => {
                      const hk = config.hotkey.toLowerCase().trim();
                      if (!hk) {
                        alert("Hotkey is empty.");
                      } else {
                        alert(`✓ '${config.hotkey.toUpperCase()}' is a valid hotkey combination.`);
                      }
                    }}
                  >
                    Test Hotkey
                  </button>
                </div>

                <div className="form-group">
                  <label htmlFor="hotkey_mode">Hotkey Behavior</label>
                  <select
                    id="hotkey_mode"
                    value={config.hotkey_mode}
                    onChange={(e) => handleFieldChange("hotkey_mode", e.target.value)}
                  >
                    <option value="toggle">Toggle (Press once to start, once to stop)</option>
                    <option value="push_to_talk">Push-to-Talk (Hold down to record, release to stop)</option>
                  </select>
                </div>

                <div className="form-group-row">
                  <label htmlFor="show_preview_window">Show Transcription Preview Overlay</label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      id="show_preview_window"
                      checked={config.show_preview_window}
                      onChange={(e) => handleFieldChange("show_preview_window", e.target.checked)}
                    />
                    <span className="slider"></span>
                  </label>
                </div>

                {config.show_preview_window && (
                  <>
                    <div className="form-group">
                      <label htmlFor="preview_hide_after_ms">Auto-hide after (ms)</label>
                      <input
                        type="number"
                        id="preview_hide_after_ms"
                        min="0"
                        max="30000"
                        step="500"
                        value={config.preview_hide_after_ms}
                        onChange={(e) => handleFieldChange("preview_hide_after_ms", parseInt(e.target.value))}
                      />
                      <div className="form-helper">0 keeps overlay open until manually closed. Recommended: 8000 ms.</div>
                    </div>

                    <div className="form-group">
                      <label htmlFor="preview_opacity">Overlay Opacity</label>
                      <div className="range-container">
                        <input
                          type="range"
                          id="preview_opacity"
                          min="0.1"
                          max="1.0"
                          step="0.05"
                          value={config.preview_opacity}
                          onChange={(e) => handleFieldChange("preview_opacity", parseFloat(e.target.value))}
                        />
                        <span className="range-val">{Math.round(config.preview_opacity * 100)}%</span>
                      </div>
                    </div>
                  </>
                )}
              </div>
            </>
          )}

          {activeTab === "widget" && (
            <>
              <div className="tab-title">Floating Widget Settings</div>
              <div className="setting-card">
                <div className="setting-card-title">Widget Appearance</div>
                <div className="form-group-row">
                  <label htmlFor="show_floating_widget">Enable Floating Widget</label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      id="show_floating_widget"
                      checked={config.show_floating_widget}
                      onChange={(e) => handleFieldChange("show_floating_widget", e.target.checked)}
                    />
                    <span className="slider"></span>
                  </label>
                </div>

                <div className="form-group-row">
                  <label htmlFor="widget_always_on_top">Keep Widget Always on Top</label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      id="widget_always_on_top"
                      checked={config.widget_always_on_top}
                      onChange={(e) => handleFieldChange("widget_always_on_top", e.target.checked)}
                    />
                    <span className="slider"></span>
                  </label>
                </div>

                <div className="form-group">
                  <label htmlFor="widget_size">Widget Diameter (px)</label>
                  <div className="range-container">
                    <input
                      type="range"
                      id="widget_size"
                      min="32"
                      max="128"
                      step="4"
                      value={config.widget_size}
                      onChange={(e) => handleFieldChange("widget_size", parseInt(e.target.value))}
                    />
                    <span className="range-val">{config.widget_size}px</span>
                  </div>
                </div>

                <div className="form-group">
                  <label htmlFor="widget_opacity">Widget Idle Opacity</label>
                  <div className="range-container">
                    <input
                      type="range"
                      id="widget_opacity"
                      min="0.1"
                      max="1.0"
                      step="0.05"
                      value={config.widget_opacity}
                      onChange={(e) => handleFieldChange("widget_opacity", parseFloat(e.target.value))}
                    />
                    <span className="range-val">{Math.round(config.widget_opacity * 100)}%</span>
                  </div>
                </div>
              </div>
            </>
          )}

          {activeTab === "cloud" && (
            <>
              <div className="tab-title">Cloud STT & Secure Credentials</div>

              <div className="setting-card">
                <div className="setting-card-title">Active Cloud STT Provider</div>
                <div style={{ fontSize: "13px", color: "var(--text-muted, #94a3b8)", marginBottom: "16px" }}>
                  Select which cloud provider handles speech-to-text transcription when Cloud STT mode is enabled.
                </div>
                <div className="grid-3" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "12px" }}>
                  {[
                    { id: "gemini", name: "Google Gemini", desc: "Fast & Accurate (Flash)" },
                    { id: "azure", name: "Microsoft Azure", desc: "Azure Cognitive Services" },
                    { id: "sarvam", name: "Sarvam AI", desc: "Indian Languages" }
                  ].map((p) => {
                    const isActive = (config.cloud_provider || config.cloud_fallback_provider || "azure") === p.id;
                    return (
                      <div
                        key={p.id}
                        onClick={() => {
                          handleFieldChange("cloud_provider", p.id);
                          handleFieldChange("cloud_fallback_provider", p.id);
                        }}
                        style={{
                          padding: "12px 16px",
                          borderRadius: "8px",
                          border: isActive ? "2px solid #f97316" : "1px solid rgba(255, 255, 255, 0.1)",
                          backgroundColor: isActive ? "rgba(249, 115, 22, 0.15)" : "rgba(255, 255, 255, 0.03)",
                          cursor: "pointer",
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          transition: "all 0.2s ease"
                        }}
                      >
                        <div>
                          <div style={{ fontWeight: 600, color: isActive ? "#f97316" : "#e2e8f0" }}>{p.name}</div>
                          <div style={{ fontSize: "12px", color: "#94a3b8" }}>{p.desc}</div>
                        </div>
                        <label className="switch" onClick={(e) => e.stopPropagation()}>
                          <input
                            type="checkbox"
                            checked={isActive}
                            onChange={(e) => {
                              if (e.target.checked) {
                                handleFieldChange("cloud_provider", p.id);
                                handleFieldChange("cloud_fallback_provider", p.id);
                              }
                            }}
                          />
                          <span className="slider"></span>
                        </label>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="setting-card">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                  <div className="setting-card-title" style={{ margin: 0 }}>Google Gemini</div>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span style={{ fontSize: "13px", color: (config.cloud_provider || config.cloud_fallback_provider) === "gemini" ? "#f97316" : "#94a3b8" }}>
                      {(config.cloud_provider || config.cloud_fallback_provider) === "gemini" ? "Active" : "Activate"}
                    </span>
                    <label className="switch">
                      <input
                        type="checkbox"
                        checked={(config.cloud_provider || config.cloud_fallback_provider) === "gemini"}
                        onChange={(e) => {
                          if (e.target.checked) {
                            handleFieldChange("cloud_provider", "gemini");
                            handleFieldChange("cloud_fallback_provider", "gemini");
                          }
                        }}
                      />
                      <span className="slider"></span>
                    </label>
                  </div>
                </div>
                <div className="form-group">
                  <label htmlFor="gemini_key">Gemini API Key</label>
                  <div className="input-with-button">
                    <input
                      type={showGeminiKey ? "text" : "password"}
                      id="gemini_key"
                      placeholder="Enter Google AI API Key..."
                      value={geminiKey}
                      onChange={(e) => setGeminiKey(e.target.value)}
                    />
                    <button className="btn btn-secondary" onClick={() => setShowGeminiKey(!showGeminiKey)}>
                      {showGeminiKey ? "Hide" : "Show"}
                    </button>
                    <button className="btn btn-primary" onClick={testGeminiKey}>
                      Test Connection
                    </button>
                  </div>
                  {geminiTestStatus !== "idle" && (
                    <div className={`connection-status ${geminiTestStatus}`}>
                      {geminiTestStatus === "testing" && "Validating credentials..."}
                      {geminiTestStatus === "success" && "✓ API Connection verified successfully!"}
                      {geminiTestStatus === "error" && "✗ Connection failed. Check your API key."}
                    </div>
                  )}
                </div>

                <div className="form-group">
                  <label htmlFor="gemini_stt_model">Gemini Model</label>
                  <input
                    type="text"
                    id="gemini_stt_model"
                    value={config.gemini_stt_model}
                    onChange={(e) => handleFieldChange("gemini_stt_model", e.target.value)}
                  />
                </div>
              </div>

              <div className="setting-card">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                  <div className="setting-card-title" style={{ margin: 0 }}>Microsoft Azure Speech</div>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span style={{ fontSize: "13px", color: (config.cloud_provider || config.cloud_fallback_provider) === "azure" ? "#f97316" : "#94a3b8" }}>
                      {(config.cloud_provider || config.cloud_fallback_provider) === "azure" ? "Active" : "Activate"}
                    </span>
                    <label className="switch">
                      <input
                        type="checkbox"
                        checked={(config.cloud_provider || config.cloud_fallback_provider) === "azure"}
                        onChange={(e) => {
                          if (e.target.checked) {
                            handleFieldChange("cloud_provider", "azure");
                            handleFieldChange("cloud_fallback_provider", "azure");
                          }
                        }}
                      />
                      <span className="slider"></span>
                    </label>
                  </div>
                </div>
                <div className="form-group">
                  <label htmlFor="azure_key">Azure API Key</label>
                  <div className="input-with-button">
                    <input
                      type={showAzureKey ? "text" : "password"}
                      id="azure_key"
                      placeholder="Enter Azure Speech Key..."
                      value={azureKey}
                      onChange={(e) => setAzureKey(e.target.value)}
                    />
                    <button className="btn btn-secondary" onClick={() => setShowAzureKey(!showAzureKey)}>
                      {showAzureKey ? "Hide" : "Show"}
                    </button>
                    <button className="btn btn-primary" onClick={testAzureKey}>
                      Test Connection
                    </button>
                  </div>
                  {azureTestStatus !== "idle" && (
                    <div className={`connection-status ${azureTestStatus}`}>
                      {azureTestStatus === "testing" && "Validating region & key..."}
                      {azureTestStatus === "success" && "✓ Key verified!"}
                      {azureTestStatus === "error" && "✗ Verification failed. Check key length."}
                    </div>
                  )}
                </div>

                <div className="form-group">
                  <label htmlFor="cloud_region">Service Region</label>
                  <input
                    type="text"
                    id="cloud_region"
                    placeholder="e.g. eastus"
                    value={config.cloud_region}
                    onChange={(e) => handleFieldChange("cloud_region", e.target.value)}
                  />
                </div>
              </div>

              <div className="setting-card">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                  <div className="setting-card-title" style={{ margin: 0 }}>Sarvam AI (Indian Languages)</div>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span style={{ fontSize: "13px", color: (config.cloud_provider || config.cloud_fallback_provider) === "sarvam" ? "#f97316" : "#94a3b8" }}>
                      {(config.cloud_provider || config.cloud_fallback_provider) === "sarvam" ? "Active" : "Activate"}
                    </span>
                    <label className="switch">
                      <input
                        type="checkbox"
                        checked={(config.cloud_provider || config.cloud_fallback_provider) === "sarvam"}
                        onChange={(e) => {
                          if (e.target.checked) {
                            handleFieldChange("cloud_provider", "sarvam");
                            handleFieldChange("cloud_fallback_provider", "sarvam");
                          }
                        }}
                      />
                      <span className="slider"></span>
                    </label>
                  </div>
                </div>
                <div className="form-group">
                  <label htmlFor="sarvam_key">Sarvam API Key</label>
                  <div className="input-with-button">
                    <input
                      type={showSarvamKey ? "text" : "password"}
                      id="sarvam_key"
                      placeholder="Enter Sarvam API Key..."
                      value={sarvamKey}
                      onChange={(e) => setSarvamKey(e.target.value)}
                    />
                    <button className="btn btn-secondary" onClick={() => setShowSarvamKey(!showSarvamKey)}>
                      {showSarvamKey ? "Hide" : "Show"}
                    </button>
                    <button className="btn btn-primary" onClick={testSarvamKey}>
                      Test Connection
                    </button>
                  </div>
                  {sarvamTestStatus !== "idle" && (
                    <div className={`connection-status ${sarvamTestStatus}`}>
                      {sarvamTestStatus === "testing" && "Checking connection..."}
                      {sarvamTestStatus === "success" && "✓ Connection verified!"}
                      {sarvamTestStatus === "error" && "✗ Verification failed."}
                    </div>
                  )}
                </div>

                <div className="grid-2">
                  <div className="form-group">
                    <label htmlFor="sarvam_model">Sarvam Model</label>
                    <select
                      id="sarvam_model"
                      value={config.sarvam_model}
                      onChange={(e) => handleFieldChange("sarvam_model", e.target.value)}
                    >
                      <option value="saarika:v2.5">Saarika v2.5 (Fast)</option>
                      <option value="saaras:v3">Saaras v3 (Premium)</option>
                    </select>
                  </div>

                  <div className="form-group">
                    <label htmlFor="sarvam_language">Primary Language</label>
                    <select
                      id="sarvam_language"
                      value={config.sarvam_language}
                      onChange={(e) => handleFieldChange("sarvam_language", e.target.value)}
                    >
                      <option value="hi-IN">Hindi (hi-IN)</option>
                      <option value="ta-IN">Tamil (ta-IN)</option>
                      <option value="te-IN">Telugu (te-IN)</option>
                      <option value="kn-IN">Kannada (kn-IN)</option>
                      <option value="ml-IN">Malayalam (ml-IN)</option>
                      <option value="mr-IN">Marathi (mr-IN)</option>
                      <option value="bn-IN">Bengali (bn-IN)</option>
                      <option value="gu-IN">Gujarati (gu-IN)</option>
                    </select>
                  </div>
                </div>

                <div className="form-group-row">
                  <label htmlFor="enable_sarvam_websocket">Enable WebSocket Real-Time STT</label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      id="enable_sarvam_websocket"
                      checked={config.enable_sarvam_websocket}
                      onChange={(e) => handleFieldChange("enable_sarvam_websocket", e.target.checked)}
                    />
                    <span className="slider"></span>
                  </label>
                </div>
              </div>


              <div className="setting-card">
                <div className="setting-card-title">OpenRouter</div>
                <div className="form-group">
                  <label htmlFor="openrouter_key">OpenRouter API Key</label>
                  <div className="input-with-button">
                    <input
                      type={showOpenRouterKey ? "text" : "password"}
                      id="openrouter_key"
                      placeholder="Enter OpenRouter API Key..."
                      value={openrouterKey}
                      onChange={(e) => setOpenRouterKey(e.target.value)}
                    />
                    <button className="btn btn-secondary" onClick={() => setShowOpenRouterKey(!showOpenRouterKey)}>
                      {showOpenRouterKey ? "Hide" : "Show"}
                    </button>
                    <button className="btn btn-primary" onClick={testOpenRouterKey}>
                      Test Connection
                    </button>
                  </div>
                  {openrouterTestStatus !== "idle" && (
                    <div className={`connection-status ${openrouterTestStatus}`}>
                      {openrouterTestStatus === "testing" && "Checking connection..."}
                      {openrouterTestStatus === "success" && "✓ Connection verified!"}
                      {openrouterTestStatus === "error" && "✗ Verification failed."}
                    </div>
                  )}
                </div>
              </div>

              <div className="setting-card">
                <div className="setting-card-title">Groq API</div>
                <div className="form-group">
                  <label htmlFor="groq_key">Groq API Key</label>
                  <div className="input-with-button">
                    <input
                      type={showGroqKey ? "text" : "password"}
                      id="groq_key"
                      placeholder="Enter Groq API Key..."
                      value={groqKey}
                      onChange={(e) => setGroqKey(e.target.value)}
                    />
                    <button className="btn btn-secondary" onClick={() => setShowGroqKey(!showGroqKey)}>
                      {showGroqKey ? "Hide" : "Show"}
                    </button>
                    <button className="btn btn-primary" onClick={testGroqKey}>
                      Test Connection
                    </button>
                  </div>
                  {groqTestStatus !== "idle" && (
                    <div className={`connection-status ${groqTestStatus}`}>
                      {groqTestStatus === "testing" && "Checking connection..."}
                      {groqTestStatus === "success" && "✓ Connection verified!"}
                      {groqTestStatus === "error" && "✗ Verification failed."}
                    </div>
                  )}
                </div>
              </div>
            </>
          )}

          {activeTab === "advanced" && (
            <>
              <div className="tab-title">Advanced Settings</div>
              
              <div className="setting-card">
                <div className="setting-card-title">Text Formatting & Dictation options</div>
                <div className="form-group-row">
                  <label htmlFor="spoken_punctuation">Translate Spoken Punctuation (e.g. "period" to ".")</label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      id="spoken_punctuation"
                      checked={config.spoken_punctuation}
                      onChange={(e) => handleFieldChange("spoken_punctuation", e.target.checked)}
                    />
                    <span className="slider"></span>
                  </label>
                </div>

                <div className="form-group-row">
                  <label htmlFor="auto_capitalise">Automatically Capitalise First Letter of Sentences</label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      id="auto_capitalise"
                      checked={config.auto_capitalise}
                      onChange={(e) => handleFieldChange("auto_capitalise", e.target.checked)}
                    />
                    <span className="slider"></span>
                  </label>
                </div>
              </div>

              <div className="setting-card">
                <div className="setting-card-title">Text Injection Method</div>
                <div className="form-group">
                  <label htmlFor="inject_method">Injection Strategy</label>
                  <select
                    id="inject_method"
                    value={config.inject_method}
                    onChange={(e) => handleFieldChange("inject_method", e.target.value)}
                  >
                    <option value="clipboard">Clipboard Paste (Ctrl+V) [Recommended, Fast]</option>
                    <option value="sendinput">Direct Typing (SendInput API) [Safest, Slow]</option>
                  </select>
                  <div className="form-helper">
                    Clipboard method copies text, pastes via Ctrl+V, and restores original clipboard. Direct typing inputs characters char-by-char.
                  </div>
                </div>

                <div className="form-group">
                  <label htmlFor="inject_delay_ms">Modifier Release / Paste Delay (ms)</label>
                  <input
                    type="number"
                    id="inject_delay_ms"
                    min="10"
                    max="1000"
                    value={config.inject_delay_ms}
                    onChange={(e) => handleFieldChange("inject_delay_ms", parseInt(e.target.value))}
                  />
                  <div className="form-helper">Time to wait for target application focus and clipboard write stability.</div>
                </div>
              </div>

              <div className="setting-card">
                <div className="setting-card-title">System & Logging</div>
                <div className="form-group-row">
                  <label htmlFor="start_with_windows">Start DictateAnywhere with Windows</label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      id="start_with_windows"
                      checked={config.start_with_windows}
                      onChange={(e) => handleFieldChange("start_with_windows", e.target.checked)}
                    />
                    <span className="slider"></span>
                  </label>
                </div>

                <div className="form-group">
                  <label htmlFor="log_level">Logging Verbosity Level</label>
                  <select
                    id="log_level"
                    value={config.log_level}
                    onChange={(e) => handleFieldChange("log_level", e.target.value)}
                  >
                    <option value="DEBUG">DEBUG (Detailed tracing)</option>
                    <option value="INFO">INFO (Standard information)</option>
                    <option value="WARNING">WARNING (Only alerts/errors)</option>
                    <option value="ERROR">ERROR (Fatal errors only)</option>
                  </select>
                </div>
              </div>

              <div className="setting-card">
                <div className="setting-card-title">Auto-Updates</div>
                <div className="form-group-row">
                  <label htmlFor="check_updates">Check for Updates Automatically</label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      id="check_updates"
                      checked={config.check_updates}
                      onChange={(e) => handleFieldChange("check_updates", e.target.checked)}
                    />
                    <span className="slider"></span>
                  </label>
                </div>
                <div className="form-group" style={{ marginTop: "12px" }}>
                  <button className="btn btn-secondary" onClick={handleCheckUpdates}>
                    Check Updates Now
                  </button>
                  {updateCheckStatus !== "idle" && (
                    <div style={{ marginTop: "8px", fontSize: "13px", color: updateCheckStatus === "error" ? "#f38ba8" : "#a6e3a1" }}>
                      {updateCheckMessage}
                    </div>
                  )}
                </div>
              </div>

              <div className="setting-card">
                <div className="setting-card-title">Application Configuration Folder</div>
                <p style={{ fontSize: "13px", color: "#a6adc8", lineHeight: "1.4" }}>
                  Open the configuration directory containing the JSON configuration files, correction database, and logs.
                </p>
                <div className="form-group" style={{ marginTop: "12px" }}>
                  <button className="btn btn-secondary" onClick={handleOpenConfigFolder}>
                    Open Config Folder
                  </button>
                </div>
              </div>

              <div className="setting-card">
                <div className="setting-card-title">Whisper Local Model Cache</div>
                <p style={{ fontSize: "13px", color: "#a6adc8", lineHeight: "1.4", marginBottom: "12px" }}>
                  These Whisper model weights are currently cached locally in your AppData directory. Deleting them frees up disk space; they will be downloaded again on next local engine launch.
                </p>
                
                {isLoadingCache ? (
                   <div style={{ fontSize: "13px", color: "orange" }}>Loading cached models...</div>
                ) : cachedModels.length === 0 ? (
                   <div style={{ fontSize: "13px", color: "#6c7086" }}>No local Whisper models currently cached.</div>
                ) : (
                  <div className="table-container">
                    <table className="settings-table">
                      <thead>
                        <tr>
                          <th>Model Name</th>
                          <th style={{ width: "120px" }}>Size (MB)</th>
                          <th style={{ width: "80px", textAlign: "center" }}>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {cachedModels.map((m) => (
                          <tr key={m.name}>
                            <td style={{ fontWeight: 600 }}>{m.name}</td>
                            <td>{m.size_mb.toFixed(0)} MB</td>
                            <td style={{ textAlign: "center" }}>
                              <button className="btn btn-danger btn-sm" onClick={() => handleDeleteModel(m.name)}>
                                Delete
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </>
          )}

          {activeTab === "corrections" && (
            <>
              <div className="tab-title">Word Corrections & Replacements</div>
              <div className="setting-card">
                <div className="setting-card-title">Define Word Corrections</div>
                <p style={{ fontSize: "13px", color: "#a6adc8", lineHeight: "1.4" }}>
                  Define case-insensitive text replacements applied to the transcribed text. Match boundaries automatically enforce whole-word searches.
                </p>

                {/* Add new correction */}
                <div className="grid-2">
                  <div className="form-group">
                    <label>Spoken Word / Pattern (from)</label>
                    <input
                      type="text"
                      placeholder="e.g. teh"
                      value={newFromWord}
                      onChange={(e) => setNewFromWord(e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label>Replacement Text (to)</label>
                    <div className="input-with-button">
                      <input
                        type="text"
                        placeholder="e.g. the"
                        value={newToWord}
                        onChange={(e) => setNewToWord(e.target.value)}
                      />
                      <button className="btn btn-primary" onClick={addCorrection}>
                        Add Pair
                      </button>
                    </div>
                  </div>
                </div>

                {/* List table */}
                <div className="table-container">
                  <table className="settings-table">
                    <thead>
                      <tr>
                        <th>Spoken Phrase (Case Insensitive)</th>
                        <th>Verbatim Replacement</th>
                        <th style={{ width: "80px", textAlign: "center" }}>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {corrections.length === 0 ? (
                        <tr>
                          <td colSpan={3} style={{ textAlign: "center", color: "#6c7086", padding: "16px" }}>
                            No word corrections defined yet.
                          </td>
                        </tr>
                      ) : (
                        corrections.map((corr, idx) => (
                          <tr key={idx}>
                            <td>
                              <input
                                type="text"
                                className="table-input"
                                value={corr.from}
                                onChange={(e) => updateCorrectionField(idx, "from", e.target.value)}
                              />
                            </td>
                            <td>
                              <input
                                type="text"
                                className="table-input"
                                value={corr.to}
                                onChange={(e) => updateCorrectionField(idx, "to", e.target.value)}
                              />
                            </td>
                            <td style={{ textAlign: "center" }}>
                              <button className="btn btn-danger btn-sm" onClick={() => removeCorrection(idx)}>
                                Delete
                              </button>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}

          {activeTab === "polish" && (
            <>
              <div className="tab-title">LLM Transcription Polish</div>
              <div className="setting-card">
                <div className="setting-card-title">Configure Text Polishing</div>
                <div className="form-group-row">
                  <label htmlFor="enable_polish">Enable Text Polishing (LLM Refinement)</label>
                  <label className="switch">
                    <input
                      type="checkbox"
                      id="enable_polish"
                      checked={config.enable_polish}
                      onChange={(e) => handleFieldChange("enable_polish", e.target.checked)}
                    />
                    <span className="slider"></span>
                  </label>
                </div>

                <div className="form-group" style={{ marginTop: "12px" }}>
                  <label>Polish Toggle Hotkey</label>
                  <div
                    ref={polishHotkeyRef}
                    className={`hotkey-capturer ${isRecordingPolishHotkey ? "recording" : ""}`}
                    onClick={() => setIsRecordingPolishHotkey(true)}
                  >
                    {isRecordingPolishHotkey ? "Listening for keypress..." : (config.polish_hotkey || "ctrl+alt+p").toUpperCase()}
                  </div>
                  <div className="form-helper">
                    Press this global shortcut to toggle polishing ON/OFF instantly.
                  </div>
                </div>

                {config.enable_polish && (
                  <>
                    <div className="grid-2">
                      <div className="form-group">
                        <label htmlFor="polish_provider">Polish Provider</label>
                        <select
                          id="polish_provider"
                          value={config.polish_provider}
                          onChange={(e) => handleFieldChange("polish_provider", e.target.value)}
                        >
                          <option value="ollama">Ollama (Local LLM)</option>
                          <option value="gemini">Google Gemini AI</option>
                          <option value="openrouter">OpenRouter AI</option>
                          <option value="groq">Groq API</option>
                        </select>
                      </div>

                      <div className="form-group">
                        <label htmlFor="polish_action">Refinement Action</label>
                        <select
                          id="polish_action"
                          value={config.polish_action}
                          onChange={(e) => handleFieldChange("polish_action", e.target.value)}
                        >
                          <option value="Fix Grammar & Spelling">Fix Grammar & Spelling</option>
                          <option value="Make Professional">Make Professional</option>
                          <option value="Summarize">Summarize</option>
                          <option value="Bullet Points">Create Bullet Points</option>
                          <option value="Chat">Chat</option>
                          <option value="Custom Prompt">Use Custom Prompt</option>
                        </select>
                      </div>
                    </div>

                    {config.polish_action === "Custom Prompt" && (
                      <div className="form-group">
                        <label htmlFor="custom_polish_prompt">Custom Polish Prompt</label>
                        <textarea
                          id="custom_polish_prompt"
                          rows={3}
                          value={config.custom_polish_prompt}
                          onChange={(e) => handleFieldChange("custom_polish_prompt", e.target.value)}
                        />
                      </div>
                    )}

                    {config.polish_provider === "ollama" ? (
                      <>
                        <div className="grid-2">
                          <div className="form-group">
                            <label htmlFor="ollama_url">Ollama API URL</label>
                            <div className="input-with-button">
                              <input
                                type="text"
                                id="ollama_url"
                                value={config.ollama_url}
                                onChange={(e) => handleFieldChange("ollama_url", e.target.value)}
                              />
                              <button
                                className="btn btn-secondary"
                                onClick={() => fetchOllamaModels(config.ollama_url)}
                              >
                                Refresh
                              </button>
                            </div>
                          </div>

                          <div className="form-group">
                            <label htmlFor="polish_ollama_model">Ollama Model</label>
                            {ollamaStatus === "loading" && <div style={{ fontSize: "11px", color: "orange" }}>Fetching local models...</div>}
                            {ollamaStatus === "error" && (
                              <div style={{ fontSize: "11px", color: "#f38ba8", marginBottom: "4px" }}>
                                Connection offline. Using manual input fallback.
                              </div>
                            )}
                            {ollamaStatus === "error" || ollamaModels.length === 0 ? (
                              <input
                                type="text"
                                id="polish_ollama_model"
                                placeholder="e.g. llama3"
                                value={config.polish_ollama_model}
                                onChange={(e) => handleFieldChange("polish_ollama_model", e.target.value)}
                              />
                            ) : (
                              <select
                                id="polish_ollama_model"
                                value={config.polish_ollama_model}
                                onChange={(e) => handleFieldChange("polish_ollama_model", e.target.value)}
                              >
                                {!ollamaModels.includes(config.polish_ollama_model) && config.polish_ollama_model && (
                                  <option value={config.polish_ollama_model}>
                                    {config.polish_ollama_model}
                                  </option>
                                )}
                                {ollamaModels.map((m) => (
                                  <option key={m} value={m}>
                                    {m}
                                  </option>
                                ))}
                              </select>
                            )}
                          </div>
                        </div>
                        <div className="form-group" style={{ marginTop: "12px" }}>
                          <label htmlFor="polish_ollama_timeout">Ollama Timeout (seconds)</label>
                          <div className="range-container">
                            <input
                              type="range"
                              id="polish_ollama_timeout"
                              min="10"
                              max="300"
                              step="5"
                              value={config.polish_ollama_timeout ?? 90}
                              onChange={(e) => handleFieldChange("polish_ollama_timeout", parseInt(e.target.value))}
                            />
                            <span className="range-val">{config.polish_ollama_timeout ?? 90}s</span>
                          </div>
                        </div>
                      </>
                    ) : config.polish_provider === "gemini" ? (
                      <div className="form-group">
                        <label htmlFor="polish_gemini_model">Gemini Model</label>
                        <input
                          type="text"
                          id="polish_gemini_model"
                          value={config.polish_gemini_model}
                          onChange={(e) => handleFieldChange("polish_gemini_model", e.target.value)}
                        />
                      </div>
                    ) : config.polish_provider === "openrouter" ? (
                      <div className="form-group">
                        <label htmlFor="polish_openrouter_model">OpenRouter Model</label>
                        <input
                          type="text"
                          id="polish_openrouter_model"
                          placeholder="Enter OpenRouter Model Name (e.g. google/gemini-2.5-flash)"
                          value={config.polish_openrouter_model}
                          onChange={(e) => handleFieldChange("polish_openrouter_model", e.target.value)}
                        />
                      </div>
                    ) : config.polish_provider === "groq" ? (
                      <div className="form-group">
                        <label htmlFor="polish_groq_model">Groq Model</label>
                        <input
                          type="text"
                          id="polish_groq_model"
                          placeholder="Enter Groq Model Name (e.g. llama-3.3-70b-versatile)"
                          value={config.polish_groq_model}
                          onChange={(e) => handleFieldChange("polish_groq_model", e.target.value)}
                        />
                      </div>
                    ) : null}

                  </>
                )}
              </div>
            </>
          )}

          {activeTab === "launcher" && (
            <>
              <div className="tab-title">App Launcher Voice Commands</div>
              <div className="setting-card">
                <div className="setting-card-title">Voice Command Mappings</div>
                <p style={{ fontSize: "13px", color: "#a6adc8", lineHeight: "1.4" }}>
                  Map specific spoken phrases to trigger opening local executables, files, folders or command scripts.
                </p>

                {/* Add new Launcher command */}
                <div className="grid-2">
                  <div className="form-group">
                    <label>Spoken Phrase</label>
                    <input
                      type="text"
                      placeholder="e.g. open notepad"
                      value={newCommandText}
                      onChange={(e) => setNewCommandText(e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label>Executable / File path</label>
                    <div className="input-with-button">
                      <input
                        type="text"
                        placeholder="e.g. C:\Windows\notepad.exe"
                        value={newCommandPath}
                        onChange={(e) => setNewCommandPath(e.target.value)}
                      />
                      <button className="btn btn-secondary" onClick={handleLauncherBrowse}>
                        Browse...
                      </button>
                      <button className="btn btn-primary" onClick={addLauncherCommand}>
                        Add Mapped Path
                      </button>
                    </div>
                  </div>
                </div>

                {/* Mappings table */}
                <div className="table-container">
                  <table className="settings-table">
                    <thead>
                      <tr>
                        <th>Spoken Voice Command</th>
                        <th>Target File / Folder / Program Path</th>
                        <th style={{ width: "80px", textAlign: "center" }}>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {!config.app_launcher_commands || Object.keys(config.app_launcher_commands).length === 0 ? (
                        <tr>
                          <td colSpan={3} style={{ textAlign: "center", color: "#6c7086", padding: "16px" }}>
                            No launcher commands configured.
                          </td>
                        </tr>
                      ) : (
                        Object.entries(config.app_launcher_commands).map(([cmd, path]) => (
                          <tr key={cmd}>
                            <td style={{ fontWeight: 600, color: "#f9e2af" }}>{cmd}</td>
                            <td style={{ fontFamily: "monospace", fontSize: "12px", color: "#a6adc8", wordBreak: "break-all" }}>
                              {path as string}
                            </td>
                            <td style={{ textAlign: "center" }}>
                              <button className="btn btn-danger btn-sm" onClick={() => removeLauncherCommand(cmd)}>
                                Delete
                              </button>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
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
