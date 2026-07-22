import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface HistoryEntry {
  id: string;
  timestamp: string;
  text: string;
  rawText?: string;
  polished?: boolean;
  polishStatus?: string;
  polishProvider?: string;
  polishModel?: string;
  polishError?: string;
}

interface HistoryState {
  entries: HistoryEntry[];
  addEntry: (
    payload:
      | string
      | {
          text: string;
          rawText?: string;
          polished?: boolean;
          polishStatus?: string;
          polishProvider?: string;
          polishModel?: string;
          polishError?: string;
        }
  ) => void;
  deleteEntry: (id: string) => void;
  clearHistory: () => void;
}

export const useHistoryStore = create<HistoryState>()(
  persist(
    (set) => ({
      entries: [],
      addEntry: (payload) =>
        set((state) => {
          const now = new Date();
          const timestamp = now.toLocaleTimeString(undefined, {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
            hour12: false,
          });
          const isString = typeof payload === "string";
          const textVal = isString ? payload : payload.text;
          const rawTextVal = isString ? undefined : payload.rawText;
          const polishedVal = isString ? undefined : payload.polished;
          const statusVal = isString ? undefined : payload.polishStatus;
          const providerVal = isString ? undefined : payload.polishProvider;
          const modelVal = isString ? undefined : payload.polishModel;
          const errorVal = isString ? undefined : payload.polishError;

          const newEntry: HistoryEntry = {
            id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
            timestamp,
            text: textVal.trim(),
            rawText: rawTextVal?.trim(),
            polished: polishedVal,
            polishStatus: statusVal,
            polishProvider: providerVal,
            polishModel: modelVal,
            polishError: errorVal,
          };
          return { entries: [newEntry, ...state.entries] };
        }),
      deleteEntry: (id) =>
        set((state) => ({
          entries: state.entries.filter((entry) => entry.id !== id),
        })),
      clearHistory: () => set({ entries: [] }),
    }),
    {
      name: "dictate-anywhere-history",
    }
  )
);
