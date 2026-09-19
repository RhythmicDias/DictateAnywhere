import React from "react";

interface HotkeysTabProps {
  config: Record<string, any>;
  handleFieldChange: (field: string, val: any) => void;
  isRecordingHotkey: boolean;
  setIsRecordingHotkey: (rec: boolean) => void;
  hotkeyRef: React.RefObject<HTMLDivElement>;
  isRecordingPolishHotkey: boolean;
  setIsRecordingPolishHotkey: (rec: boolean) => void;
  polishHotkeyRef: React.RefObject<HTMLDivElement>;
}

export const HotkeysTab: React.FC<HotkeysTabProps> = ({
  config,
  handleFieldChange,
  isRecordingHotkey,
  setIsRecordingHotkey,
  hotkeyRef,
  isRecordingPolishHotkey,
  setIsRecordingPolishHotkey,
  polishHotkeyRef,
}) => {
  return (
    <>
      <div className="tab-title">Global Shortcut Settings</div>
      <div className="setting-card">
        <div className="setting-card-title">Hotkey Configuration</div>
        <div className="form-group">
          <label>Press to Capture Hotkey Combination</label>
          <div
            ref={hotkeyRef}
            className={`hotkey-capturer ${isRecordingHotkey ? "recording" : ""}`}
            onClick={() => setIsRecordingHotkey(true)}
          >
            {isRecordingHotkey ? "Listening for keypress..." : config.hotkey.toUpperCase()}
          </div>
          <div className="form-helper">
            Click the box above and press your desired shortcut (e.g., Ctrl+Alt+D).
          </div>
        </div>
        <div className="form-group">
          <button
            className="btn btn-secondary"
            onClick={() => {
              const hk = config.hotkey.toLowerCase().trim();
              if (!hk) {
                alert("Hotkey is empty.");
              } else {
                alert(`✓ '${config.hotkey.toUpperCase()}' is a valid hotkey combination.`);
              }
            }}
          >
            Test Hotkey
          </button>
        </div>

        <div className="form-group">
          <label htmlFor="hotkey_mode">Hotkey Behavior</label>
          <select
            id="hotkey_mode"
            value={config.hotkey_mode}
            onChange={(e) => handleFieldChange("hotkey_mode", e.target.value)}
          >
            <option value="toggle">Toggle (Press once to start, once to stop)</option>
            <option value="push_to_talk">Push-to-Talk (Hold down to record, release to stop)</option>
          </select>
        </div>

        <div className="form-group-row">
          <label htmlFor="show_preview_window">Show Transcription Preview Overlay</label>
          <label className="switch">
            <input
              type="checkbox"
              id="show_preview_window"
              checked={config.show_preview_window}
              onChange={(e) => handleFieldChange("show_preview_window", e.target.checked)}
            />
            <span className="slider"></span>
          </label>
        </div>

        {config.show_preview_window && (
          <>
            <div className="form-group">
              <label htmlFor="preview_hide_after_ms">Auto-hide after (ms)</label>
              <input
                type="number"
                id="preview_hide_after_ms"
                min="0"
                max="30000"
                step="500"
                value={config.preview_hide_after_ms}
                onChange={(e) => handleFieldChange("preview_hide_after_ms", parseInt(e.target.value))}
              />
              <div className="form-helper">0 keeps overlay open until manually closed. Recommended: 8000 ms.</div>
            </div>

            <div className="form-group">
              <label htmlFor="preview_opacity">Overlay Opacity</label>
              <div className="range-container">
                <input
                  type="range"
                  id="preview_opacity"
                  min="0.1"
                  max="1.0"
                  step="0.05"
                  value={config.preview_opacity}
                  onChange={(e) => handleFieldChange("preview_opacity", parseFloat(e.target.value))}
                />
                <span className="range-val">{Math.round(config.preview_opacity * 100)}%</span>
              </div>
            </div>
          </>
        )}

        <div className="form-group" style={{ marginTop: "12px" }}>
          <label>Polish Toggle Hotkey</label>
          <div
            ref={polishHotkeyRef}
            className={`hotkey-capturer ${isRecordingPolishHotkey ? "recording" : ""}`}
            onClick={() => setIsRecordingPolishHotkey(true)}
          >
            {isRecordingPolishHotkey ? "Listening for keypress..." : (config.polish_hotkey || "ctrl+alt+p").toUpperCase()}
          </div>
          <div className="form-helper">
            Press this global shortcut to toggle text polishing ON/OFF instantly.
          </div>
        </div>
      </div>
    </>
  );
};
