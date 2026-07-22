import { useEffect, useState } from "react";
import { useHistoryStore } from "../../store/historyStore";
import { exportTextFile } from "../../lib/commands";
import "./HistoryWindow.css";

export default function HistoryWindow() {
  const { entries, deleteEntry, clearHistory } = useHistoryStore();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [copiedAll, setCopiedAll] = useState(false);
  const [copiedRaw, setCopiedRaw] = useState(false);
  const [copiedFinal, setCopiedFinal] = useState(false);
  const [elapsed, setElapsed] = useState("0m 0s");
  const [sessionDate, setSessionDate] = useState("");

  // ── Session Time Tracking ──────────────────────────────────────────────────
  useEffect(() => {
    const start = Date.now();
    const now = new Date();
    setSessionDate(now.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" }));

    const updateTimer = () => {
      const diff = Math.floor((Date.now() - start) / 1000);
      const hrs = Math.floor(diff / 3600);
      const mins = Math.floor((diff % 3600) / 60);
      const secs = diff % 60;
      setElapsed(hrs > 0 ? `${hrs}h ${mins}m` : `${mins}m ${secs}s`);
    };

    updateTimer();
    const interval = setInterval(updateTimer, 1000);
    return () => clearInterval(interval);
  }, []);

  // ── Synchronize History Store Across Windows ──────────────────────────────
  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === "dictate-anywhere-history") {
        useHistoryStore.persist.rehydrate();
      }
    };
    window.addEventListener("storage", handleStorageChange);
    return () => window.removeEventListener("storage", handleStorageChange);
  }, []);

  // ── Filter Entries by Search Query ─────────────────────────────────────────
  const qLower = searchQuery.toLowerCase().trim();
  const filteredEntries = qLower
    ? entries.filter(
        (e) =>
          e.text.toLowerCase().includes(qLower) ||
          (e.rawText && e.rawText.toLowerCase().includes(qLower))
      )
    : entries;

  // Determine active entry
  const activeEntry = filteredEntries.find((e) => e.id === selectedId) || filteredEntries[0] || null;

  // ── Actions ────────────────────────────────────────────────────────────────
  const handleCopyRawText = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedRaw(true);
      setTimeout(() => setCopiedRaw(false), 2000);
    } catch (e) {
      console.error("Failed to copy raw text:", e);
    }
  };

  const handleCopyFinalText = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedFinal(true);
      setTimeout(() => setCopiedFinal(false), 2000);
    } catch (e) {
      console.error("Failed to copy final text:", e);
    }
  };

  const handleCopyAll = async () => {
    if (entries.length === 0) return;
    try {
      const formatted = entries
        .map((e) => {
          const rawPart = e.rawText ? ` [Raw: ${e.rawText}]` : "";
          const statusPart = e.polished ? ` [Polished (${e.polishStatus}) via ${e.polishProvider}]` : "";
          return `[${e.timestamp}] ${e.text}${rawPart}${statusPart}`;
        })
        .join("\n");
      await navigator.clipboard.writeText(formatted);
      setCopiedAll(true);
      setTimeout(() => setCopiedAll(false), 2000);
    } catch (e) {
      console.error("Failed to copy all entries:", e);
    }
  };

  const handleClearHistory = () => {
    if (entries.length === 0) return;
    if (
      confirm(
        `Are you sure you want to delete all ${entries.length} history entries?\nThis action cannot be undone.`
      )
    ) {
      clearHistory();
      setSelectedId(null);
    }
  };

  const handleExport = async () => {
    if (entries.length === 0) return;
    try {
      const stamp = new Date().toISOString().slice(0, 10).replace(/-/g, "");
      const nowStr = new Date().toLocaleString();
      const exportText =
        `DictateAnywhere — Transcription History\nExport Date: ${nowStr}\nEntries Count: ${entries.length}\n` +
        `─`.repeat(60) +
        `\n\n` +
        entries
          .map((e) => {
            const rawLine = e.rawText && e.rawText !== e.text ? `  Raw Whisper:  ${e.rawText}\n` : "";
            const polishLine = e.polished
              ? `  Polish Info:  ${e.polishStatus} via ${e.polishProvider} (${e.polishModel || "default"})\n`
              : "";
            return `[${e.timestamp}]\n  Final Text:   ${e.text}\n${rawLine}${polishLine}`;
          })
          .join("\n" + `─`.repeat(40) + "\n\n");

      const savedPath = await exportTextFile(exportText, `dictation_history_${stamp}.txt`);
      if (savedPath) {
        console.log("Successfully exported history to:", savedPath);
      }
    } catch (e) {
      console.error("Failed to export history:", e);
    }
  };

  // ── Regex Highlight Parser ─────────────────────────────────────────────────
  const renderHighlightedText = (text: string, query: string) => {
    if (!query) return text;
    const escapedQuery = query.replace(/[-[\]{}()*+?.,\\^$|#\s]/g, "\\$&");
    const regex = new RegExp(`(${escapedQuery})`, "gi");
    const parts = text.split(regex);

    return parts.map((part, index) =>
      regex.test(part) ? (
        <span key={index} className="match-highlight">
          {part}
        </span>
      ) : (
        part
      )
    );
  };

  return (
    <div className="history-root">
      {/* Top Search & Toolbar Panel */}
      <div className="history-toolbar">
        <div className="search-container">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#585b70" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            type="text"
            className="search-input"
            placeholder="Search transcriptions..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {searchQuery && (
            <button className="btn-clear-search" onClick={() => setSearchQuery("")} title="Clear search">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          )}
        </div>

        <div className="toolbar-actions">
          <button className="btn btn-secondary btn-sm" onClick={handleExport} disabled={entries.length === 0} title="Export history as text file">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 4 }}>
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            Export…
          </button>
          <button className="btn btn-secondary btn-sm" onClick={handleCopyAll} disabled={entries.length === 0} title="Copy all history entries to clipboard">
            {copiedAll ? (
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#a6e3a1" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 4 }}>
                <polyline points="20 6 9 17 4 12" />
              </svg>
            ) : (
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 4 }}>
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
              </svg>
            )}
            {copiedAll ? "Copied!" : "Copy All"}
          </button>
          <button className="btn btn-danger btn-sm" onClick={handleClearHistory} disabled={entries.length === 0} title="Clear all history">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 4 }}>
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
              <line x1="10" y1="11" x2="10" y2="17" />
              <line x1="14" y1="11" x2="14" y2="17" />
            </svg>
            Clear
          </button>
        </div>
      </div>

      {/* Split Screen Container */}
      <div className="history-split-container">
        {/* Left Panel: Scrollable entries list */}
        <div className="history-list-pane">
          {filteredEntries.length === 0 ? (
            <div className="empty-state">
              <svg className="empty-state-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                <line x1="16" y1="2" x2="16" y2="6" />
                <line x1="8" y1="2" x2="8" y2="6" />
                <line x1="3" y1="10" x2="21" y2="10" />
                <path d="M8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01M16 18h.01" />
              </svg>
              <div className="empty-state-title">
                {searchQuery ? "No matches" : "Empty history"}
              </div>
            </div>
          ) : (
            filteredEntries.map((entry) => (
              <div
                key={entry.id}
                className={`history-list-card ${activeEntry?.id === entry.id ? "active" : ""}`}
                onClick={() => setSelectedId(entry.id)}
              >
                <div className="card-item-meta">
                  <span className="card-item-timestamp">[{entry.timestamp}]</span>
                  {entry.polished && (
                    <span
                      className={`card-item-badge ${
                        entry.polishStatus === "success" ? "success" : "failed"
                      }`}
                      title={
                        entry.polishStatus === "success"
                          ? `Polished via ${entry.polishProvider}`
                          : `Polish failed: ${entry.polishError}`
                      }
                    >
                      {entry.polishStatus === "success" ? "✨" : "⚠️"}
                    </span>
                  )}
                </div>
                <div className="card-item-snippet">
                  {entry.text.length > 80 ? entry.text.slice(0, 80) + "…" : entry.text}
                </div>
                
                <button
                  className="btn-card-delete"
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteEntry(entry.id);
                    if (selectedId === entry.id) {
                      setSelectedId(null);
                    }
                  }}
                  title="Delete entry"
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="3 6 5 6 21 6" />
                    <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
                  </svg>
                </button>
              </div>
            ))
          )}
        </div>

        {/* Right Panel: Detail split-screen comparison */}
        <div className="history-detail-pane">
          {activeEntry ? (
            <div className="detail-view-container">
              {/* Header with Badges and Details Actions */}
              <div className="detail-header">
                <div className="detail-header-info">
                  <div className="detail-timestamp">[{activeEntry.timestamp}]</div>
                  <div className="detail-badges">
                    <span className="badge-engine">STT Engine</span>
                    {activeEntry.polished ? (
                      activeEntry.polishStatus === "success" ? (
                        <span className="badge-polish success">
                          ✨ Polished ({activeEntry.polishProvider})
                        </span>
                      ) : (
                        <span className="badge-polish failed" title={activeEntry.polishError}>
                          ⚠️ Polish Failed
                        </span>
                      )
                    ) : (
                      <span className="badge-polish disabled">No Polish</span>
                    )}
                  </div>
                </div>

                <div className="detail-header-actions">
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => handleCopyFinalText(activeEntry.text)}
                    title="Copy final text"
                  >
                    {copiedFinal ? "Copied!" : "Copy Final"}
                  </button>
                  <button
                    className="btn btn-danger btn-sm"
                    onClick={() => {
                      deleteEntry(activeEntry.id);
                      setSelectedId(null);
                    }}
                    title="Delete entry"
                  >
                    Delete
                  </button>
                </div>
              </div>

              {/* Comparison Section (Before and After Side-by-Side) */}
              <div className="comparison-panels">
                {/* Left side: Before */}
                <div className="comparison-card before-card">
                  <div className="comp-card-header">
                    <span className="comp-card-title">Before (Raw Whisper)</span>
                    <button
                      className="btn-comp-copy"
                      onClick={() => handleCopyRawText(activeEntry.rawText || activeEntry.text)}
                    >
                      {copiedRaw ? "Copied!" : "Copy"}
                    </button>
                  </div>
                  <div className="comp-card-body">
                    {renderHighlightedText(activeEntry.rawText || activeEntry.text, searchQuery)}
                  </div>
                </div>

                {/* Right side: After */}
                <div className="comparison-card after-card">
                  <div className="comp-card-header">
                    <span className="comp-card-title">
                      {activeEntry.polished && activeEntry.polishStatus === "success"
                        ? "After (Polished Text)"
                        : "After (Final Output)"}
                    </span>
                    <button
                      className="btn-comp-copy"
                      onClick={() => handleCopyFinalText(activeEntry.text)}
                    >
                      {copiedFinal ? "Copied!" : "Copy"}
                    </button>
                  </div>
                  <div className="comp-card-body">
                    {renderHighlightedText(activeEntry.text, searchQuery)}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="detail-empty-state">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="empty-icon">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              <div className="empty-title">No Entry Selected</div>
              <div className="empty-desc">Select an entry from the list to view its Whisper transcription and AI polishing comparisons.</div>
            </div>
          )}
        </div>
      </div>

      {/* Footer Status Bar */}
      <div className="history-footer">
        <div>
          {searchQuery ? (
            <span>
              Showing {filteredEntries.length} of {entries.length} matches
            </span>
          ) : (
            <span>
              {entries.length} {entries.length === 1 ? "entry" : "entries"} recorded
            </span>
          )}
        </div>
        <div>
          Session started {sessionDate} · Running {elapsed}
        </div>
      </div>
    </div>
  );
}
