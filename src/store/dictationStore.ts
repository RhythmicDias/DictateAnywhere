import { create } from "zustand";

export type DictationState =
  | "idle"
  | "active"
  | "loading"
  | "polishing"
  | "error"
  | "injecting";

interface DictationStore {
  state: DictationState;
  setState: (s: DictationState) => void;
  /** Toggle between idle and active */
  toggle: () => void;
}

export const useDictationStore = create<DictationStore>((set, get) => ({
  state: "loading",
  setState: (s) => set({ state: s }),
  toggle: () => {
    const current = get().state;
    if (current === "idle" || current === "error") {
      set({ state: "active" });
    } else if (current === "active" || current === "injecting") {
      set({ state: "idle" });
    }
  },
}));
