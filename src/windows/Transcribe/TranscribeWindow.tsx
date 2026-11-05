import { useEffect, useState } from "react";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { listen } from "@tauri-apps/api/event";
import {
  getConfig,
  selectAudioFile,
  transcribeAudioFile,
  exportTextFile,
} from "../../lib/commands";
import "./TranscribeWindow.css";

const SUPPORTED_EXTENSIONS = [
  "wav", "mp3", "m4a", "flac", "ogg", "opus", "aac", "wma", "webm", "mp4", "mkv",
];

function extractBaseName(filePath: string): string {
  const parts = filePath.replace(/\\/g, "/").split("/");
  const fileName = parts[parts.length - 1] || "audio";
  return fileName.replace(/\.[^/.]+$/, "");
}

export default function TranscribeWindow() {
  const [filePath, setFilePath] = useState<string>("");
  const [language, setLanguage] = useState<string>("auto");
  const [includeTimestamps, setIncludeTimestamps] = useState<boolean>(false);
  const [applyPolish, setApplyPolish] = useState<boolean>(false);

  const [isTranscribing, setIsTranscribing] = useState<boolean>(false);
  const [progressPct, setProgressPct] = useState<number>(0);
  const [progressStatus, setProgressStatus] = useState<string>("");
  const [errorMsg, setErrorMsg] = useState<string>("");

  const [transcript, setTranscript] = useState<string>("");
  const [durationMs, setDurationMs] = useState<number | null>(null);
  const [copied, setCopied] = useState<boolean>(false);
  const [savedPath, setSavedPath] = useState<string>("");
  const [isDragging, setIsDragging] = useState<boolean>(false);

  // Load default language & polish state from config
  useEffect(() => {
    getConfig()
      .then((cfg) => {
        if (cfg) {
          if (typeof cfg.language === "string") setLanguage(cfg.language);
          if (typeof cfg.enable_polish === "boolean") setApplyPolish(cfg.enable_polish);
        }
      })
      .catch(console.error);
  }, []);

  // Listen for sidecar file transcription events & Tauri file drag-drop
  useEffect(() => {
    let unlistenProgress: (() => void) | null = null;
    let unlistenResult: (() => void) | null = null;
    let unlistenError: (() => void) | null = null;
    let unlistenDrop: (() => void) | null = null;

    const setup = async () => {
      unlistenProgress = await listen<any>("dictation://file-progress", (e) => {
        const p = e.payload || {};
        if (typeof p.percent === "number") setProgressPct(p.percent);
        if (typeof p.status === "string") setProgressStatus(p.status);
        if (typeof p.partial_text === "string" && p.partial_text) {
          setTranscript(p.partial_text);
        }
      });

      unlistenResult = await listen<any>("dictation://file-result", (e) => {
        const p = e.payload || {};
        setIsTranscribing(false);
        setProgressPct(100);
        setProgressStatus("Completed");
        setTranscript(p.text || "");
        if (typeof p.duration_ms === "number") {
          setDurationMs(p.duration_ms);
        }
      });

      unlistenError = await listen<any>("dictation://file-error", (e) => {
        setIsTranscribing(false);
        setErrorMsg(typeof e.payload === "string" ? e.payload : String(e.payload));
      });

      try {
        unlistenDrop = await getCurrentWindow().onDragDropEvent((event) => {
          if (event.payload.type === "over") {
            setIsDragging(true);
          } else if (event.payload.type === "leave") {
            setIsDragging(false);
          } else if (event.payload.type === "drop") {
            setIsDragging(false);
            const dropped = event.payload.paths?.[0];
            if (dropped) {
              const ext = dropped.split(".").pop()?.toLowerCase() || "";
              if (SUPPORTED_EXTENSIONS.includes(ext)) {
                setFilePath(dropped);
                setErrorMsg("");
                setSavedPath("");
              } else {
                setErrorMsg(`Unsupported file format (.${ext}). Supported: ${SUPPORTED_EXTENSIONS.join(", ")}`);
              }
            }
          }
        });
      } catch {
        // Ignore if running outside native webview
      }
    };

    setup().catch(console.error);

    return () => {
      unlistenProgress?.();
      unlistenResult?.();
      unlistenError?.();
      unlistenDrop?.();
    };
  }, []);

  const handleBrowse = async () => {
    if (isTranscribing) return;
    try {
      const selected = await selectAudioFile();
      if (selected) {
        setFilePath(selected);
        setErrorMsg("");
        setSavedPath("");
      }
    } catch (err) {
      setErrorMsg(`Failed to select file: ${err}`);
    }
  };

  const handleStartTranscription = async () => {
    if (!filePath || isTranscribing) return;
    setErrorMsg("");
    setSavedPath("");
    setDurationMs(null);
    setTranscript("");
    setIsTranscribing(true);
    setProgressPct(1);
    setProgressStatus("Starting offline transcription...");

    try {
      await transcribeAudioFile(filePath, includeTimestamps, applyPolish, language);
    } catch (err) {
      setIsTranscribing(false);
      setErrorMsg(typeof err === "string" ? err : String(err));
    }
  };

  const handleCopy = async () => {
    if (!transcript) return;
    try {
      await navigator.clipboard.writeText(transcript);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy transcript:", err);
    }
  };

  const handleSaveTxt = async () => {
    if (!transcript) return;
    try {
      const base = filePath ? extractBaseName(filePath) : "transcription";
      const defaultName = `${base}_transcript.txt`;
      const saved = await exportTextFile(transcript, defaultName);
      if (saved) {
        setSavedPath(saved);
      }
    } catch (err) {
      setErrorMsg(`Failed to save .txt file: ${err}`);
    }
  };

  const fileName = filePath ? filePath.replace(/\\/g, "/").split("/").pop() : "";

  return (
    <div className="transcribe-root">
      {/* Header */}
      <div className="transcribe-header">
        <div className="transcribe-title-group">
          <h2 className="transcribe-title">Offline Audio Transcription</h2>
          <div className="transcribe-subtitle">
            Local Whisper GPU/CPU engine · Exports clean UTF-8 .txt
          </div>
        </div>
        <button
          className="t-btn t-btn-secondary"
          onClick={handleBrowse}
          disabled={isTranscribing}
        >
          Browse Audio…
        </button>
      </div>

      {/* Main Content */}
      <div className="transcribe-body">
        {/* Upload / Dropzone */}
        <div
          className={`file-dropzone ${filePath ? "has-file" : ""} ${isDragging ? "dragging" : ""}`}
          onClick={handleBrowse}
        >
          <div className="file-dropzone-info">
            <div className="file-icon-box">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 18V5l12-2v13" />
                <circle cx="6" cy="18" r="3" />
                <circle cx="18" cy="16" r="3" />
              </svg>
            </div>
            <div className="file-details">
              <div className="file-name">
                {fileName || "Click to select or drag & drop an audio file"}
              </div>
              <div className="file-formats-hint" title={filePath || undefined}>
                {filePath
                  ? filePath
                  : "Supports .wav, .mp3, .m4a, .flac, .ogg, .opus, .aac, .wma, .webm, .mp4, .mkv"}
              </div>
            </div>
          </div>

          <button
            className="t-btn t-btn-primary"
            onClick={(e) => {
              e.stopPropagation();
              handleStartTranscription();
            }}
            disabled={!filePath || isTranscribing}
          >
            {isTranscribing ? "Transcribing…" : "Transcribe Now"}
          </button>
        </div>

        {/* Options Row */}
        <div className="options-row">
          <div className="options-left">
            <label className="option-item">
              <span>Language:</span>
              <select
                className="option-select"
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                disabled={isTranscribing}
              >
                <option value="auto">Auto-detect</option>
                <option value="en">English (en)</option>
                <option value="es">Spanish (es)</option>
                <option value="fr">French (fr)</option>
                <option value="de">German (de)</option>
                <option value="it">Italian (it)</option>
                <option value="pt">Portuguese (pt)</option>
                <option value="hi">Hindi (hi)</option>
                <option value="ja">Japanese (ja)</option>
                <option value="zh">Chinese (zh)</option>
                <option value="ru">Russian (ru)</option>
                <option value="ar">Arabic (ar)</option>
              </select>
            </label>

            <label className="option-item" title="Prefix each segment with [MM:SS - MM:SS]">
              <input
                type="checkbox"
                checked={includeTimestamps}
                onChange={(e) => setIncludeTimestamps(e.target.checked)}
                disabled={isTranscribing}
              />
              <span>Include [MM:SS] Timestamps</span>
            </label>

            <label className="option-item" title="Run configured AI Text Polish after transcription">
              <input
                type="checkbox"
                checked={applyPolish}
                onChange={(e) => setApplyPolish(e.target.checked)}
                disabled={isTranscribing}
              />
              <span>Apply AI Polish</span>
            </label>
          </div>
        </div>

        {/* Progress Bar */}
        {isTranscribing && (
          <div className="progress-box">
            <div className="progress-header">
              <span>{progressStatus || "Transcribing..."}</span>
              <span>{progressPct}%</span>
            </div>
            <div className="progress-track">
              <div className="progress-fill" style={{ width: `${progressPct}%` }} />
            </div>
          </div>
        )}

        {/* Error Banner */}
        {errorMsg && <div className="error-banner">{errorMsg}</div>}

        {/* Transcript Output Box */}
        <div className="output-container">
          <div className="output-toolbar">
            <span className="output-label">Transcription Output (.txt preview)</span>
            <span className="output-meta">
              {durationMs !== null
                ? `Processed in ${(durationMs / 1000).toFixed(1)}s · ${transcript.length} chars`
                : transcript
                ? `${transcript.length} chars`
                : "Ready"}
            </span>
          </div>
          <textarea
            className="output-textarea"
            placeholder="Transcribed text will stream here automatically. You can edit it before saving as a .txt file..."
            value={transcript}
            onChange={(e) => setTranscript(e.target.value)}
          />
        </div>
      </div>

      {/* Footer */}
      <div className="transcribe-footer">
        <div className="footer-status">
          {savedPath ? `✓ Saved to ${savedPath}` : "Also saved automatically to Session History"}
        </div>
        <div className="footer-buttons">
          <button
            className="t-btn t-btn-secondary"
            onClick={handleCopy}
            disabled={!transcript}
          >
            {copied ? "✓ Copied!" : "Copy Text"}
          </button>
          <button
            className="t-btn t-btn-dark"
            onClick={handleSaveTxt}
            disabled={!transcript}
          >
            Save as .txt…
          </button>
        </div>
      </div>
    </div>
  );
}

