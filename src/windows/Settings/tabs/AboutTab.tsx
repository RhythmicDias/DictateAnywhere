import React, { useEffect, useState } from "react";
import { getVersion } from "@tauri-apps/api/app";
import { open } from "@tauri-apps/plugin-shell";

interface AboutTabProps {
  config: Record<string, any>;
  handleFieldChange: (field: string, val: any) => void;
  handleCheckUpdates: () => void;
  updateCheckStatus: "idle" | "checking" | "success" | "error";
  updateCheckMessage: string;
  updateReleaseUrl?: string;
}

const REPO_URL = "https://github.com/RhythmicDias/DictateAnywhere";
const RELEASES_URL = "https://github.com/RhythmicDias/DictateAnywhere/releases";
const ISSUES_URL = "https://github.com/RhythmicDias/DictateAnywhere/issues";

export const AboutTab: React.FC<AboutTabProps> = ({
  config,
  handleFieldChange,
  handleCheckUpdates,
  updateCheckStatus,
  updateCheckMessage,
  updateReleaseUrl,
}) => {
  const [appVersion, setAppVersion] = useState("2.0.4");

  useEffect(() => {
    getVersion()
      .then((v) => {
        if (v) setAppVersion(v);
      })
      .catch(() => {});
  }, []);

  const openExternal = async (url: string) => {
    try {
      await open(url);
    } catch {
      window.open(url, "_blank", "noopener,noreferrer");
    }
  };

  return (
    <>
      <div className="tab-title">About DictateAnywhere</div>

      {/* App Identity Card */}
      <div className="setting-card" style={{ padding: "14px 16px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <div
            style={{
              width: "48px",
              height: "48px",
              borderRadius: "12px",
              background: "linear-gradient(135deg, #2a8f8e 0%, #1f6b6a 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
              boxShadow: "0 2px 8px rgba(42, 143, 142, 0.25)",
            }}
          >
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              <line x1="12" x2="12" y1="19" y2="22" />
              <line x1="8" x2="16" y1="22" y2="22" />
            </svg>
          </div>

          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
              <span style={{ fontSize: "16px", fontWeight: 700, color: "var(--text-primary)" }}>
                DictateAnywhere
              </span>
              <span
                style={{
                  fontSize: "11px",
                  fontWeight: 600,
                  padding: "2px 8px",
                  borderRadius: "999px",
                  background: "rgba(42, 143, 142, 0.14)",
                  color: "var(--accent-primary)",
                }}
              >
                v{appVersion}
              </span>
              <span
                style={{
                  fontSize: "11px",
                  fontWeight: 500,
                  padding: "2px 8px",
                  borderRadius: "999px",
                  background: "var(--bg-pill)",
                  color: "var(--text-secondary)",
                }}
              >
                MIT License
              </span>
            </div>
            <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "4px", lineHeight: 1.45 }}>
              High-performance, privacy-first hybrid voice dictation for Windows and macOS. Injects transcribed speech directly at your cursor in any active application.
            </div>
          </div>
        </div>

        <div
          style={{
            display: "flex",
            gap: "8px",
            marginTop: "12px",
            paddingTop: "10px",
            borderTop: "1px solid var(--border-subtle)",
            flexWrap: "wrap",
          }}
        >
          <button className="btn btn-secondary" onClick={() => openExternal(REPO_URL)}>
            GitHub Repository
          </button>
          <button className="btn btn-secondary" onClick={() => openExternal(RELEASES_URL)}>
            Releases & Changelog
          </button>
          <button className="btn btn-secondary" onClick={() => openExternal(ISSUES_URL)}>
            Report an Issue
          </button>
        </div>
      </div>

      {/* Software Updates Card */}
      <div className="setting-card">
        <div className="setting-card-title">Software Updates</div>
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

        <div className="form-group" style={{ paddingTop: "8px", paddingBottom: "10px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
            <button
              className="btn btn-secondary"
              onClick={handleCheckUpdates}
              disabled={updateCheckStatus === "checking"}
            >
              {updateCheckStatus === "checking" ? "Checking…" : "Check for Updates"}
            </button>

            {updateReleaseUrl && (
              <button
                className="btn btn-primary"
                onClick={() => openExternal(updateReleaseUrl)}
              >
                Download Latest Release
              </button>
            )}
          </div>

          {updateCheckStatus !== "idle" && (
            <div
              className={`connection-status ${
                updateCheckStatus === "checking"
                  ? "testing"
                  : updateCheckStatus === "error"
                  ? "error"
                  : "success"
              }`}
              style={{ marginTop: "6px", fontSize: "12px" }}
            >
              {updateCheckMessage}
            </div>
          )}
        </div>
      </div>

      {/* Architecture & Capabilities Card */}
      <div className="setting-card">
        <div className="setting-card-title">Application Details & Capabilities</div>
        <div className="form-group-row">
          <label>Author & Maintainer</label>
          <span style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: 500 }}>
            Stephen Dias (RhythmicDias)
          </span>
        </div>
        <div className="form-group-row">
          <label>Runtime Architecture</label>
          <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
            Tauri v2 (Rust Core + React UI + Python Sidecar)
          </span>
        </div>
        <div className="form-group-row">
          <label>Local STT Engine</label>
          <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
            faster-whisper (CUDA Tensor Core & CPU int8/float16)
          </span>
        </div>
        <div className="form-group-row">
          <label>Cloud STT Providers</label>
          <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
            Google Gemini, Groq, OpenRouter, Azure Speech, Sarvam AI
          </span>
        </div>
        <div className="form-group-row">
          <label>AI Polish & Translation</label>
          <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
            Ollama & Cloud LLMs (105+ languages, 35+ writing scripts)
          </span>
        </div>
      </div>
    </>
  );
};
