import { useEffect, useState } from "react";
import { listen, emit, type UnlistenFn } from "@tauri-apps/api/event";
import { type DictationState, useDictationStore } from "../store/dictationStore";

/** Set up all Tauri event listeners for the FloatingWidget / global state.
 *  Returns an async cleanup function — call it in useEffect's return. */
export async function setupDictationListeners(): Promise<UnlistenFn> {
  const { setState } = useDictationStore.getState();

  const unlistenToggle = await listen("dictation://toggle", () => {
    const currentState = useDictationStore.getState().state;
    if (currentState === "idle" || currentState === "error") {
      emit("dictation://start", {}).catch(console.error);
    } else {
      emit("dictation://stop", {}).catch(console.error);
    }
  });

  const unlistenStart = await listen("dictation://start", () => {
    setState("active");
  });

  const unlistenStop = await listen("dictation://stop", () => {
    setState("idle");
  });

  const unlistenStateChanged = await listen<DictationState>(
    "dictation://state-changed",
    (event) => {
      setState(event.payload);
    }
  );

  // Return a single cleanup fn that removes all listeners
  return () => {
    unlistenToggle();
    unlistenStart();
    unlistenStop();
    unlistenStateChanged();
  };
}

/**
 * Custom React hook to detect window focus, system wake, and timer time jumps.
 * Returns an incrementing counter value that triggers re-subscriptions when it changes.
 */
export function useWakeRecovery(): number {
  const [trigger, setTrigger] = useState(0);

  useEffect(() => {
    let active = true;

    const handleWake = () => {
      if (active) {
        setTrigger((prev) => prev + 1);
      }
    };

    // 1. Re-subscribe when the window gains focus
    window.addEventListener("focus", handleWake);

    // 2. Re-subscribe when receiving system://wake event from Rust backend
    let unlistenWake: (() => void) | null = null;
    listen("system://wake", () => {
      console.log("[WakeRecovery] system://wake event received — triggering listener recovery");
      handleWake();
    }).then((un) => {
      if (active) {
        unlistenWake = un;
      } else {
        un();
      }
    });

    // 3. Fallback sleep/wake detector using high-latency timer check
    let lastTime = Date.now();
    const interval = setInterval(() => {
      const now = Date.now();
      // If interval missed by more than 8 seconds, system slept
      if (now - lastTime > 8000) {
        console.log(`[WakeRecovery] Time jump detected (${now - lastTime}ms) — triggering listener recovery`);
        handleWake();
      }
      lastTime = now;
    }, 2000);

    return () => {
      active = false;
      window.removeEventListener("focus", handleWake);
      clearInterval(interval);
      if (unlistenWake) unlistenWake();
    };
  }, []);

  return trigger;
}
