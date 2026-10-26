/**
 * FloatingWidget.tsx
 *
 * 64×64 always-on-top, transparent, draggable microphone button.
 * Replaces floating_widget.py (Tkinter canvas with PNG icons).
 *
 * States:   idle (blue) | active (red + pulse) | loading (amber) | error (grey)
 * Drag:     mousedown → appWindow.startDragging() — no manual offset math needed
 * Events:   listens for dictation://toggle, dictation://start, dictation://stop
 */

import { useEffect, useRef, useState } from "react";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { listen, emit } from "@tauri-apps/api/event";
import { useDictationStore, type DictationState } from "../../store/dictationStore";
import { setupDictationListeners, useWakeRecovery } from "../../lib/events";
import { getConfig, setWidgetMenuOpen } from "../../lib/commands";
import "./FloatingWidget.css";

// ── Colour palette (matches Python floating_widget.py) ─────────────────────
const COLOURS: Record<DictationState, { bg: string; ring: string; glow: string }> = {
  idle:      { bg: "#d97706", ring: "#f59e0b", glow: "rgba(217,119,6,0.5)" },
  active:    { bg: "#e63946", ring: "#ff6b7a", glow: "rgba(230,57,70,0.6)"  },
  loading:   { bg: "#f5b089", ring: "#ffcbb0", glow: "rgba(245,176,137,0.5)" },
  polishing: { bg: "#b4befe", ring: "#cba6f7", glow: "rgba(180,190,254,0.4)" },
  error:     { bg: "#6c757d", ring: "#9ea7ad", glow: "rgba(108,117,125,0.4)"},
  injecting: { bg: "#d97706", ring: "#f59e0b", glow: "rgba(217,119,6,0.5)" },
};

// ── Context menu definition ─────────────────────────────────────────────────
interface MenuItem {
  id: string;
  label: string;
  danger?: boolean;
  separator?: boolean;
  disabledWhen?: DictationState[];
}

const MENU_ITEMS: MenuItem[] = [
  { id: "start",          label: "Start Dictation",      disabledWhen: ["active"] },
  { id: "stop",           label: "Stop Dictation",       disabledWhen: ["idle", "loading", "polishing", "error", "injecting"] },
  { id: "sep1",           label: "",                     separator: true },
  { id: "toggle_preview", label: "Toggle Preview"        },
  { id: "history",        label: "Session History…"      },
  { id: "settings",       label: "Settings…"             },
  { id: "sep2",           label: "",                     separator: true },
  { id: "quit",           label: "Quit",                 danger: true   },
];

// ── Mic path (simple SVG microphone icon) ───────────────────────────────────
function MicPath({ color }: { color: string }) {
  return (
    <g fill={color}>
      {/* Microphone body */}
      <rect x="27" y="16" width="10" height="18" rx="5" ry="5" />
      {/* Stand */}
      <path d="M20 30 a12 12 0 0 0 24 0" fill="none" stroke={color} strokeWidth="2.5" strokeLinecap="round" />
      {/* Stem */}
      <line x1="32" y1="42" x2="32" y2="48" stroke={color} strokeWidth="2.5" strokeLinecap="round" />
      {/* Base */}
      <line x1="26" y1="48" x2="38" y2="48" stroke={color} strokeWidth="2.5" strokeLinecap="round" />
    </g>
  );
}

// ── Countdown arc (SVG stroke-dashoffset technique) ─────────────────────────
function CountdownArc({ fraction }: { fraction: number }) {
  const R = 27.25;
  const circumference = 2 * Math.PI * R;
  const dash = circumference * Math.max(0, Math.min(1, fraction));
  const color = fraction > 0.5 ? "#4CAF50" : fraction > 0.2 ? "#FFC107" : "#FF5252";
  return (
    <circle
      cx="32" cy="32" r={R}
      fill="none"
      stroke={color}
      strokeWidth="3"
      strokeDasharray={`${dash} ${circumference}`}
      strokeLinecap="round"
      // Start at 12 o'clock (rotate -90°)
      transform="rotate(-90 32 32)"
      style={{ transition: "stroke-dasharray 0.15s linear" }}
    />
  );
}

// ── Main component ──────────────────────────────────────────────────────────
export default function FloatingWidget() {
  const { state, setState } = useDictationStore();
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number } | null>(null);
  const [micPos, setMicPos] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [countdown, setCountdown] = useState<number>(1); // 1 = full, 0 = empty
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef<number>(0);
  const maxSecondsRef = useRef<number>(30);

  const [widgetSize, setWidgetSize] = useState<number>(64);
  const [widgetOpacity, setWidgetOpacity] = useState<number>(0.85);
  const [maxSeconds, setMaxSeconds] = useState<number>(30);

  const widgetSizeRef = useRef<number>(64);
  const micPosRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const dragStartRef = useRef<{ x: number; y: number } | null>(null);
  const didDragRef = useRef<boolean>(false);

  const col = COLOURS[state];
  const wakeTrigger = useWakeRecovery();

  function closeContextMenu(sizeOverride?: number) {
    const targetSize = sizeOverride ?? widgetSizeRef.current;
    setContextMenu(null);
    setMicPos({ x: 0, y: 0 });
    micPosRef.current = { x: 0, y: 0 };
    setWidgetMenuOpen(false, targetSize, 0, 0).catch(console.error);
  }

  // ── Subscribe to Tauri events & config ────────────────────────────────────
  useEffect(() => {
    let active = true;
    let cleanup: (() => void) | null = null;

    setupDictationListeners().then((fn) => {
      if (active) {
        cleanup = fn;
      } else {
        fn();
      }
    });

    // Load config on mount
    getConfig()
      .then((cfg) => {
        if (!active) return;
        if (cfg) {
          const size = Number(cfg.widget_size) || 64;
          const opacity = Number(cfg.widget_opacity) || 0.85;
          const maxSec = Number(cfg.max_record_seconds) || 30;
          widgetSizeRef.current = size;
          setWidgetSize(size);
          setWidgetOpacity(opacity);
          setMaxSeconds(maxSec);
        }
      })
      .catch(console.error);

    // Listen to live changes
    let unlistenConfig: (() => void) | null = null;
    listen<any>("config://changed", (event) => {
      if (!active) return;
      const cfg = event.payload;
      if (cfg) {
        const size = Number(cfg.widget_size) || 64;
        const opacity = Number(cfg.widget_opacity) || 0.85;
        const maxSec = Number(cfg.max_record_seconds) || 30;
        widgetSizeRef.current = size;
        setContextMenu(null);
        setMicPos({ x: 0, y: 0 });
        micPosRef.current = { x: 0, y: 0 };
        setWidgetSize(size);
        setWidgetOpacity(opacity);
        setMaxSeconds(maxSec);
      }
    }).then((un) => {
      if (active) {
        unlistenConfig = un;
      } else {
        un();
      }
    });

    return () => {
      active = false;
      cleanup?.();
      unlistenConfig?.();
    };
  }, [wakeTrigger]);

  // ── Close context menu on window blur or Escape ───────────────────────────
  useEffect(() => {
    if (!contextMenu) return;

    const handleBlur = () => closeContextMenu();
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeContextMenu();
    };

    window.addEventListener("blur", handleBlur);
    window.addEventListener("keydown", handleKeyDown);

    let unlistenFocus: (() => void) | null = null;
    getCurrentWindow()
      .onFocusChanged(({ payload: focused }) => {
        if (!focused) closeContextMenu();
      })
      .then((un) => {
        unlistenFocus = un;
      })
      .catch(console.error);

    return () => {
      window.removeEventListener("blur", handleBlur);
      window.removeEventListener("keydown", handleKeyDown);
      unlistenFocus?.();
    };
  }, [contextMenu]);

  // ── Countdown timer (active state) ────────────────────────────────────────
  useEffect(() => {
    if (state === "active") {
      startTimeRef.current = Date.now();
      maxSecondsRef.current = maxSeconds; // read from config
      setCountdown(1);
      countdownRef.current = setInterval(() => {
        const elapsed = (Date.now() - startTimeRef.current) / 1000;
        const fraction = Math.max(0, 1 - elapsed / maxSecondsRef.current);
        setCountdown(fraction);
      }, 50);
    } else {
      if (countdownRef.current) {
        clearInterval(countdownRef.current);
        countdownRef.current = null;
      }
      setCountdown(1);
    }
    return () => {
      if (countdownRef.current) clearInterval(countdownRef.current);
    };
  }, [state]);

  // ── Drag: delegate to Tauri window manager after 4px threshold ───────────
  function handleMouseDown(e: React.MouseEvent) {
    if (e.button !== 0 || contextMenu) return; // left button only when menu closed
    dragStartRef.current = { x: e.screenX, y: e.screenY };
    didDragRef.current = false;
  }

  function handleMouseMove(e: React.MouseEvent) {
    if (!dragStartRef.current || (e.buttons & 1) === 0) return;
    const dx = e.screenX - dragStartRef.current.x;
    const dy = e.screenY - dragStartRef.current.y;
    if (Math.hypot(dx, dy) > 4) {
      dragStartRef.current = null;
      didDragRef.current = true;
      getCurrentWindow().startDragging().catch(console.error);
    }
  }

  function handleMouseUp() {
    dragStartRef.current = null;
  }

  // ── Context menu ──────────────────────────────────────────────────────────
  async function handleContextMenu(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    const clickX = Math.max(0, Math.min(widgetSize, e.clientX - micPosRef.current.x));
    const clickY = Math.max(0, Math.min(widgetSize, e.clientY - micPosRef.current.y));
    try {
      const layout = await setWidgetMenuOpen(true, widgetSize, clickX, clickY);
      const nextMicPos = { x: layout.mic_x, y: layout.mic_y };
      micPosRef.current = nextMicPos;
      setMicPos(nextMicPos);
      setContextMenu({ x: layout.menu_x, y: layout.menu_y });
    } catch (err) {
      console.error(err);
      setContextMenu({ x: clickX, y: clickY });
    }
  }

  async function handleMenuAction(id: string) {
    closeContextMenu();
    switch (id) {
      case "start":
        setState("active");
        await emit("dictation://start", {});
        break;
      case "stop":
        setState("idle");
        await emit("dictation://stop", {});
        break;
      case "toggle_preview":
        await emit("window://toggle", { label: "preview" });
        break;
      case "history":
        await emit("window://show", { label: "history" });
        break;
      case "settings":
        await emit("window://show", { label: "settings" });
        break;
      case "quit":
        await emit("app://quit", {});
        break;
    }
  }

  // ── Click = toggle dictation ──────────────────────────────────────────────
  function handleClick() {
    if (didDragRef.current) {
      didDragRef.current = false;
      return;
    }
    if (contextMenu) {
      closeContextMenu();
      return;
    }
    if (state === "idle" || state === "error") {
      setState("active");
      emit("dictation://start", {}).catch(console.error);
    } else if (state === "active" || state === "injecting") {
      setState("idle");
      emit("dictation://stop", {}).catch(console.error);
    }
  }

  return (
    <div className="widget-root" onContextMenu={handleContextMenu}>
      <div
        className="mic-button"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onClick={handleClick}
        style={{
          left: `${micPos.x}px`,
          top: `${micPos.y}px`,
          width: `${widgetSize}px`,
          height: `${widgetSize}px`,
          opacity: state === "idle" ? widgetOpacity : 1,
        }}
      >
        <svg className="mic-svg" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
          {/* Pulse ring — only shown when active */}
          {state === "active" && (
            <circle
              className="pulse-ring"
              cx="32" cy="32" r="27"
              fill="none"
              stroke={col.ring}
              strokeWidth="2"
              opacity="0.6"
            />
          )}

          {/* Main circle */}
          <circle
            className="mic-circle"
            cx="32" cy="32" r="28"
            fill={col.bg}
          />

          {/* Ring border */}
          <circle
            cx="32" cy="32" r="27.25"
            fill="none"
            stroke={col.ring}
            strokeWidth="1.5"
            opacity="0.6"
          />

          {/* Countdown arc (active state only) */}
          {state === "active" && <CountdownArc fraction={countdown} />}

          {/* Microphone icon */}
          {state === "loading" ? (
            /* Loading spinner dots */
            <g fill="white" opacity="0.9">
              <circle cx="24" cy="32" r="3"><animate attributeName="opacity" values="1;0.2;1" dur="1s" begin="0s" repeatCount="indefinite"/></circle>
              <circle cx="32" cy="32" r="3"><animate attributeName="opacity" values="1;0.2;1" dur="1s" begin="0.3s" repeatCount="indefinite"/></circle>
              <circle cx="40" cy="32" r="3"><animate attributeName="opacity" values="1;0.2;1" dur="1s" begin="0.6s" repeatCount="indefinite"/></circle>
            </g>
          ) : state === "error" ? (
            /* Error cross */
            <g stroke="white" strokeWidth="3" strokeLinecap="round" opacity="0.9">
              <line x1="24" y1="24" x2="40" y2="40" />
              <line x1="40" y1="24" x2="24" y2="40" />
            </g>
          ) : (
            <MicPath color="rgba(255,255,255,0.95)" />
          )}
        </svg>
      </div>

      {/* Context menu */}
      {contextMenu && (
        <>
          {/* Invisible backdrop to catch outside clicks */}
          <div
            style={{ position: "fixed", inset: 0, zIndex: 9998 }}
            onMouseDown={(e) => e.stopPropagation()}
            onClick={(e) => {
              e.stopPropagation();
              closeContextMenu();
            }}
          />
          <div
            className="context-menu"
            style={{ left: `${contextMenu.x}px`, top: `${contextMenu.y}px` }}
            onMouseDown={(e) => e.stopPropagation()}
            onClick={(e) => e.stopPropagation()}
          >
            {MENU_ITEMS.map((item) => {
              if (item.separator) {
                return <div key={item.id} className="context-menu-separator" />;
              }
              const isDisabled = item.disabledWhen?.includes(state) ?? false;
              return (
                <div
                  key={item.id}
                  className={[
                    "context-menu-item",
                    isDisabled ? "disabled" : "",
                    item.danger ? "danger" : "",
                  ].join(" ")}
                  onClick={() => !isDisabled && handleMenuAction(item.id)}
                >
                  {item.label}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
