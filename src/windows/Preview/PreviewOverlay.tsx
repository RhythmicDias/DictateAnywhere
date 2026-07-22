import { useEffect, useRef, useState } from "react";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { listen, emit } from "@tauri-apps/api/event";
import { getConfig } from "../../lib/commands";
import { useDictationStore, type DictationState } from "../../store/dictationStore";
import { useWakeRecovery } from "../../lib/events";
import "./PreviewOverlay.css";

// ── Symmetrical equalizer configuration ──────────────────────────────────────
const BARS_COUNT = 15;
const CENTER_INDEX = 7;
const SIGMA = 3.0; // controls the bell curve width

export default function PreviewOverlay() {
  const { state, setState } = useDictationStore();
  const [statusText, setStatusText] = useState("Ready");
  const [toast, setToast] = useState<{ text: string; color: string } | null>(null);
  const [config, setConfig] = useState({
    show_preview_window: true,
    preview_hide_after_ms: 8000,
    preview_opacity: 0.85,
  });

  const barsRef = useRef<(HTMLDivElement | null)[]>([]);
  const audioLevelRef = useRef(0.0);
  const smoothedLevelRef = useRef(0.0);
  const animationFrameRef = useRef<number | null>(null);
  const hideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wakeTrigger = useWakeRecovery();

  // ── Load configuration on mount ────────────────────────────────────────────
  const loadConfig = async () => {
    try {
      const cfg = await getConfig();
      setConfig({
        show_preview_window: cfg.show_preview_window !== false,
        preview_hide_after_ms: isNaN(Number(cfg.preview_hide_after_ms)) ? 8000 : Number(cfg.preview_hide_after_ms),
        preview_opacity: isNaN(Number(cfg.preview_opacity)) ? 0.85 : Number(cfg.preview_opacity),
      });
    } catch (e) {
      console.error("Failed to load config in PreviewOverlay:", e);
    }
  };

  const stateRef = useRef(state);
  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  useEffect(() => {
    loadConfig();

    let active = true;
    let unlistenConfig: (() => void) | null = null;
    
    // Listen to live config changes
    listen<any>("config://changed", (event) => {
      if (!active) return;
      const cfg = event.payload;
      setConfig({
        show_preview_window: cfg.show_preview_window !== false,
        preview_hide_after_ms: isNaN(Number(cfg.preview_hide_after_ms)) ? 8000 : Number(cfg.preview_hide_after_ms),
        preview_opacity: isNaN(Number(cfg.preview_opacity)) ? 0.85 : Number(cfg.preview_opacity),
      });
    }).then((un) => {
      if (active) {
        unlistenConfig = un;
      } else {
        un();
      }
    });

    return () => {
      active = false;
      if (unlistenConfig) {
        unlistenConfig();
      }
    };
  }, [wakeTrigger]);

  // ── Listen to Tauri audio levels & state events ─────────────────────────────
  useEffect(() => {
    let active = true;
    let unlistenLevel: (() => void) | null = null;
    let unlistenState: (() => void) | null = null;

    listen<number>("dictation://audio-level", (event) => {
      if (!active) return;
      audioLevelRef.current = event.payload;
    }).then((un) => {
      if (active) {
        unlistenLevel = un;
      } else {
        un();
      }
    });

    listen<DictationState>("dictation://state-changed", (event) => {
      if (!active) return;
      setState(event.payload);
    }).then((un) => {
      if (active) {
        unlistenState = un;
      } else {
        un();
      }
    });

    return () => {
      active = false;
      if (unlistenLevel) unlistenLevel();
      if (unlistenState) unlistenState();
    };
  }, [setState, wakeTrigger]);

  // ── Listen to Polish hotkey toggling ─────────────────────────────────────────
  useEffect(() => {
    let active = true;
    let unlistenPolish: (() => void) | null = null;

    listen<boolean>("dictation://polish-toggled", (event) => {
      if (!active) return;
      const isEnabled = event.payload;
      setToast({
        text: isEnabled ? "Text Polish: ON" : "Text Polish: OFF",
        color: isEnabled ? "#a6e3a1" : "#f38ba8",
      });

      const win = getCurrentWindow();
      win.show().catch(console.error);

      if (hideTimerRef.current) {
        clearTimeout(hideTimerRef.current);
      }

      hideTimerRef.current = setTimeout(() => {
        if (!active) return;
        setToast(null);
        // Only hide if we are idle or error (not actively recording)
        if (stateRef.current === "idle" || stateRef.current === "error") {
          win.hide().catch(console.error);
        }
      }, 2500);
    }).then((un) => {
      if (active) {
        unlistenPolish = un;
      } else {
        un();
      }
    });

    return () => {
      active = false;
      if (unlistenPolish) {
        unlistenPolish();
      }
    };
  }, [wakeTrigger]);

  // ── Listen to transcription results for polish notifications ───────────────
  useEffect(() => {
    let active = true;
    let unlistenResult: (() => void) | null = null;

    listen<any>("dictation://transcription-result", (event) => {
      if (!active) return;
      const payload = event.payload;
      if (!payload || typeof payload === "string") return;

      const { polished, polish_status, polish_error, polish_provider } = payload;
      if (!polished) return;

      const win = getCurrentWindow();
      win.show().catch(console.error);

      if (hideTimerRef.current) {
        clearTimeout(hideTimerRef.current);
      }

      if (polish_status === "failed") {
        let errDesc = "API Error";
        if (polish_error) {
          if (polish_error.includes("429")) {
            errDesc = "Overloaded (429)";
          } else if (polish_error.includes("403") || polish_error.includes("key")) {
            errDesc = "Invalid API Key";
          } else {
            errDesc = polish_error.slice(0, 25);
          }
        }
        setToast({
          text: `⚠️ Polish Failed: ${errDesc} (Raw Injected)`,
          color: "#fab387", // Warning peach
        });
      } else if (polish_status === "success") {
        let providerName = "Ollama";
        if (polish_provider === "gemini") providerName = "Gemini";
        else if (polish_provider === "openrouter") providerName = "OpenRouter";
        else if (polish_provider === "groq") providerName = "Groq";
        setToast({
          text: `✨ Polished via ${providerName}`,
          color: "#a6e3a1", // Success green
        });
      }


      hideTimerRef.current = setTimeout(() => {
        if (!active) return;
        setToast(null);
        if (stateRef.current === "idle" || stateRef.current === "error") {
          win.hide().catch(console.error);
        }
      }, 4500);
    }).then((un) => {
      if (active) {
        unlistenResult = un;
      } else {
        un();
      }
    });

    return () => {
      active = false;
      if (unlistenResult) {
        unlistenResult();
      }
    };
  }, [wakeTrigger]);

  // ── Watch dictation state changes for hide/show flows ──────────────────────
  useEffect(() => {
    // Determine status text based on state
    if (state === "active") {
      setStatusText("Listening…");
      setToast(null); // Clear previous toast when starting dictation
    } else if (state === "loading") {
      setStatusText("Transcribing…");
      setToast(null); // Clear toast when transcription starts
    } else if (state === "polishing") {
      setStatusText("Polishing…");
      setToast(null); // Clear toast when polishing starts
    } else if (state === "injecting") {
      setStatusText("Injected");
    } else if (state === "error") {
      setStatusText("Error");
    } else {
      setStatusText("Ready");
    }

    // Cancel active hide timer
    if (hideTimerRef.current) {
      clearTimeout(hideTimerRef.current);
      hideTimerRef.current = null;
    }

    const win = getCurrentWindow();

    if (state === "active") {
      // Show window when recording starts
      if (config.show_preview_window) {
        win.show().catch(console.error);
      }
    } else if (state === "loading" || state === "polishing" || state === "injecting") {
      // Keep visible if already showing, but do not call win.show() to prevent popping up at startup
    } else if (state === "idle" || state === "error") {
      // Auto-hide after config timeout
      if (config.preview_hide_after_ms > 0) {
        hideTimerRef.current = setTimeout(() => {
          win.hide().catch(console.error);
        }, config.preview_hide_after_ms);
      } else if (config.preview_hide_after_ms === 0) {
        // Keep open indefinitely
      } else {
        win.hide().catch(console.error);
      }
    }
  }, [state, config.show_preview_window, config.preview_hide_after_ms]);

  // ── Symmetrical Equalizer Animation Loop (requestAnimationFrame) ───────────
  useEffect(() => {
    const isRunning = state === "active";

    const updateBars = () => {
      // Smoothen the level with interpolation decay, using square-root scaling to boost low-level audio
      const rawLevel = audioLevelRef.current;
      const target = Math.min(1.0, Math.sqrt(rawLevel) * 3.5);
      smoothedLevelRef.current = smoothedLevelRef.current * 0.78 + target * 0.22;

      const currentLvl = smoothedLevelRef.current;
      const timeSec = Date.now() / 1000;

      for (let i = 0; i < BARS_COUNT; i++) {
        const bar = barsRef.current[i];
        if (!bar) continue;

        const distance = Math.abs(i - CENTER_INDEX);
        // Gaussian curve weight
        const weight = Math.exp(-(distance * distance) / (2 * SIGMA * SIGMA));

        // Smooth wave noise multiplier to simulate dynamic frequencies
        const noise = Math.sin(timeSec * 12 + i * 0.75) * 0.08 + Math.cos(timeSec * 5 - i * 0.4) * 0.04;
        const finalLevel = isRunning ? Math.max(0.02, currentLvl + noise) : 0.02;

        // Peak height limit 32px (container height is 56px, vertical space is 36px)
        const h = 4 + 28 * finalLevel * weight;

        // Custom purple-to-cyan gradient
        const hue = 180 + (distance / CENTER_INDEX) * 105;

        bar.style.height = `${h}px`;
        bar.style.backgroundColor = `hsl(${hue}, 85%, 65%)`;
        bar.style.boxShadow = `0 0 8px hsl(${hue}, 80%, 60%, 0.45)`;
      }

      if (isRunning || smoothedLevelRef.current > 0.01) {
        animationFrameRef.current = requestAnimationFrame(updateBars);
      } else {
        // Reset bars to baseline
        for (let i = 0; i < BARS_COUNT; i++) {
          const bar = barsRef.current[i];
          if (bar) {
            const distance = Math.abs(i - CENTER_INDEX);
            const hue = 180 + (distance / CENTER_INDEX) * 105;
            bar.style.height = "4px";
            bar.style.backgroundColor = `hsl(${hue}, 85%, 65%)`;
            bar.style.boxShadow = "none";
          }
        }
        animationFrameRef.current = null;
      }
    };

    if (isRunning) {
      if (!animationFrameRef.current) {
        animationFrameRef.current = requestAnimationFrame(updateBars);
      }
    } else {
      // Decay visualizer bars smoothly even after recording stops
      if (!animationFrameRef.current && smoothedLevelRef.current > 0.01) {
        animationFrameRef.current = requestAnimationFrame(updateBars);
      }
    }

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
    };
  }, [state]);

  // ── Drag Window Handler ───────────────────────────────────────────────────
  const handleMouseDown = (e: React.MouseEvent) => {
    // Allow dragging only with Left Mouse Button, excluding interactive control buttons
    const target = e.target as HTMLElement;
    if (e.button === 0 && !target.closest(".btn-close") && !target.closest(".btn-action")) {
      e.preventDefault();
      getCurrentWindow().startDragging().catch(console.error);
    }
  };

  const handleCloseClick = async () => {
    const win = getCurrentWindow();
    await win.hide();
  };

  const handleActionClick = async () => {
    if (state === "active") {
      setState("idle");
      await emit("dictation://stop", {});
    }
  };

  return (
    <div
      className={`preview-root state-${state}`}
      onMouseDown={handleMouseDown}
      style={{
        background: `rgba(26, 26, 36, ${config.preview_opacity})`,
      }}
    >
      {/* Cancel Button (Left) */}
      <div className="btn-close" onClick={handleCloseClick} title="Cancel Overlay">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </div>

      {/* Symmetrical Soundwave (Center) */}
      <div className="equalizer-container">
        {toast ? (
          <span className="status-text state-active" style={{ color: toast.color }}>
            {toast.text}
          </span>
        ) : state === "active" ? (
          Array.from({ length: BARS_COUNT }).map((_, i) => (
            <div
              key={i}
              className="eq-bar"
              ref={(el) => (barsRef.current[i] = el)}
            />
          ))
        ) : (
          <span className={`status-text state-${state}`}>{statusText}</span>
        )}
      </div>

      {/* State / Stop Button (Right) */}
      <button
        className={`btn-action state-${state}`}
        onClick={handleActionClick}
        disabled={state !== "active"}
        title={state === "active" ? "Stop Dictation" : statusText}
      >
        {state === "active" && (
          <svg width="10" height="10" viewBox="0 0 24 24">
            <rect x="2" y="2" width="20" height="20" rx="4" fill="currentColor" />
          </svg>
        )}
        {(state === "loading" || state === "polishing") && (
          <svg className="spinner" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="2" x2="12" y2="6" />
            <line x1="12" y1="18" x2="12" y2="22" />
            <line x1="4.93" y1="4.93" x2="7.76" y2="7.76" />
            <line x1="16.24" y1="16.24" x2="19.07" y2="19.07" />
            <line x1="2" y1="12" x2="6" y2="12" />
            <line x1="18" y1="12" x2="22" y2="12" />
            <line x1="4.93" y1="19.07" x2="7.76" y2="16.24" />
            <line x1="16.24" y1="7.76" x2="19.07" y2="4.93" />
          </svg>
        )}
        {state === "injecting" && (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 6 9 17 4 12" />
          </svg>
        )}
        {state === "error" && (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
        )}
        {state === "idle" && (
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: "currentColor" }} />
        )}
      </button>
    </div>
  );
}
