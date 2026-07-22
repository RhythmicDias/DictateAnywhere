import { lazy, Suspense, useEffect } from "react";
import { useHistoryStore } from "./store/historyStore";

// Lazy-load each window component so only the relevant bundle is loaded
// in each WebView instance. The ?window= query param routes to the right UI.
const FloatingWidget = lazy(
  () => import("./windows/FloatingWidget/FloatingWidget")
);
const SettingsWindow = lazy(
  () => import("./windows/Settings/SettingsWindow")
);
const PreviewOverlay = lazy(
  () => import("./windows/Preview/PreviewOverlay")
);
const HistoryWindow = lazy(
  () => import("./windows/History/HistoryWindow")
);

function getWindowLabel(): string {
  const params = new URLSearchParams(window.location.search);
  return params.get("window") ?? "main";
}

export default function App() {
  const windowLabel = getWindowLabel();

  useEffect(() => {
    if (windowLabel !== "main") return;

    let unlistenFn: (() => void) | null = null;

    const setupListener = async () => {
      const { listen } = await import("@tauri-apps/api/event");
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
    <Suspense fallback={null}>
      {windowLabel === "floating-widget" && <FloatingWidget />}
      {windowLabel === "settings" && <SettingsWindow />}
      {windowLabel === "preview" && <PreviewOverlay />}
      {windowLabel === "history" && <HistoryWindow />}
      {/* main window is invisible — no UI needed */}
    </Suspense>
  );
}
