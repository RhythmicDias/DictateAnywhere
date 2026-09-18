import { Component, useEffect, useState, type ErrorInfo, type ReactNode } from "react";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { listen } from "@tauri-apps/api/event";
import { useHistoryStore } from "./store/historyStore";
import FloatingWidget from "./windows/FloatingWidget/FloatingWidget";
import SettingsWindow from "./windows/Settings/SettingsWindow";
import PreviewOverlay from "./windows/Preview/PreviewOverlay";
import HistoryWindow from "./windows/History/HistoryWindow";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("[ErrorBoundary] Caught error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: "24px",
          color: "#fdf8f5",
          backgroundColor: "#141210",
          fontFamily: "system-ui, sans-serif",
          height: "100vh",
          boxSizing: "border-box",
          overflow: "auto"
        }}>
          <h2 style={{ color: "#f38ba8", margin: "0 0 12px 0" }}>⚠️ Window Render Error</h2>
          <p style={{ color: "#bcaea3", fontSize: "14px", lineHeight: "1.5" }}>
            DictateAnywhere encountered an unexpected error while rendering this view:
          </p>
          <pre style={{
            background: "#1c1815",
            padding: "12px",
            borderRadius: "6px",
            border: "1px solid rgba(255,255,255,0.1)",
            color: "#f5b089",
            fontSize: "12px",
            whiteSpace: "pre-wrap",
            wordBreak: "break-word"
          }}>
            {this.state.error?.message || String(this.state.error)}
            {"\n\n"}
            {this.state.error?.stack}
          </pre>
          <button
            onClick={() => window.location.reload()}
            style={{
              marginTop: "12px",
              padding: "8px 16px",
              background: "#d97706",
              border: "none",
              borderRadius: "4px",
              color: "#fff",
              cursor: "pointer",
              fontWeight: 600
            }}
          >
            Reload Window
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

function resolveWindowLabel(): string {
  // 1. Native Tauri window label (100% reliable within Tauri webviews)
  try {
    const currentWin = getCurrentWindow();
    if (currentWin && currentWin.label) {
      return currentWin.label;
    }
  } catch {
    // Running in standalone browser
  }

  // 2. Query param ?window=...
  const params = new URLSearchParams(window.location.search);
  const qWindow = params.get("window");
  if (qWindow) return qWindow;

  // 3. Hash #window=... or #...
  const hash = window.location.hash.replace(/^#/, "");
  if (hash) {
    const hashParams = new URLSearchParams(hash);
    const hWindow = hashParams.get("window");
    if (hWindow) return hWindow;
    if (["floating-widget", "settings", "preview", "history"].includes(hash)) {
      return hash;
    }
  }

  return "floating-widget";
}

export default function App() {
  const [windowLabel] = useState<string>(() => resolveWindowLabel());

  useEffect(() => {
    if (windowLabel !== "floating-widget") return;

    let unlistenFn: (() => void) | null = null;

    const setupListener = async () => {
      const unlisten = await listen<any>("dictation://transcription-result", (event) => {
        const payload = event.payload;
        if (!payload) return;

        let text = "";
        let rawText = "";
        let polished = false;
        let polishStatus = "";
        let polishProvider = "";
        let polishModel = "";
        let polishError = "";

        if (typeof payload === "string") {
          text = payload;
        } else {
          text = payload.text || "";
          rawText = payload.raw_text || "";
          polished = payload.polished || false;
          polishStatus = payload.polish_status || "";
          polishProvider = payload.polish_provider || "";
          polishModel = payload.polish_model || "";
          polishError = payload.polish_error || "";
        }

        if (text && text.trim().length > 0) {
          useHistoryStore.getState().addEntry({
            text,
            rawText,
            polished,
            polishStatus,
            polishProvider,
            polishModel,
            polishError,
          });
        }
      });
      unlistenFn = unlisten;
    };

    setupListener().catch(console.error);

    return () => {
      if (unlistenFn) unlistenFn();
    };
  }, [windowLabel]);

  return (
    <ErrorBoundary>
      {windowLabel === "settings" && <SettingsWindow />}
      {windowLabel === "preview" && <PreviewOverlay />}
      {windowLabel === "history" && <HistoryWindow />}
      {windowLabel === "floating-widget" && <FloatingWidget />}
    </ErrorBoundary>
  );
}
