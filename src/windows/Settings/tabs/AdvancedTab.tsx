import React from "react";
import { ModelCacheInfo } from "../../../lib/commands";

interface AdvancedTabProps {
  config: Record<string, any>;
  handleFieldChange: (field: string, val: any) => void;
  handleCheckUpdates: () => void;
  updateCheckStatus: string;
  updateCheckMessage: string;
  handleOpenConfigFolder: () => void;
  isLoadingCache: boolean;
  cachedModels: ModelCacheInfo[];
  handleDeleteModel: (name: string) => void;
}

export const AdvancedTab: React.FC<AdvancedTabProps> = ({
  config,
  handleFieldChange,
  handleCheckUpdates,
  updateCheckStatus,
  updateCheckMessage,
  handleOpenConfigFolder,
  isLoadingCache,
  cachedModels,
  handleDeleteModel,
}) => {
  return (
    <>
      <div className="tab-title">Advanced Settings</div>
      
      <div className="setting-card">
        <div className="setting-card-title">Text Formatting & Dictation options</div>
        <div className="form-group-row">
          <label htmlFor="spoken_punctuation">Translate Spoken Punctuation (e.g. "period" to ".")</label>
          <label className="switch">
            <input
              type="checkbox"
              id="spoken_punctuation"
              checked={config.spoken_punctuation}
              onChange={(e) => handleFieldChange("spoken_punctuation", e.target.checked)}
            />
            <span className="slider"></span>
          </label>
        </div>

        <div className="form-group-row">
          <label htmlFor="auto_capitalise">Automatically Capitalise First Letter of Sentences</label>
          <label className="switch">
            <input
              type="checkbox"
              id="auto_capitalise"
              checked={config.auto_capitalise}
              onChange={(e) => handleFieldChange("auto_capitalise", e.target.checked)}
            />
            <span className="slider"></span>
          </label>
        </div>
      </div>

      <div className="setting-card">
        <div className="setting-card-title">Text Injection Method</div>
        <div className="form-group">
          <label htmlFor="inject_method">Injection Strategy</label>
          <select
            id="inject_method"
            value={config.inject_method}
            onChange={(e) => handleFieldChange("inject_method", e.target.value)}
          >
            <option value="clipboard">Clipboard Paste (Ctrl+V) [Recommended, Fast]</option>
            <option value="sendinput">Direct Typing (SendInput API) [Safest, Slow]</option>
          </select>
          <div className="form-helper">
            Clipboard method copies text, pastes via Ctrl+V, and restores original clipboard. Direct typing inputs characters char-by-char.
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="inject_delay_ms">Modifier Release / Paste Delay (ms)</label>
          <input
            type="number"
            id="inject_delay_ms"
            min="10"
            max="1000"
            value={config.inject_delay_ms}
            onChange={(e) => handleFieldChange("inject_delay_ms", parseInt(e.target.value))}
          />
          <div className="form-helper">Time to wait for target application focus and clipboard write stability.</div>
        </div>
      </div>

      <div className="setting-card">
        <div className="setting-card-title">System & Logging</div>
        <div className="form-group-row">
          <label htmlFor="start_with_windows">Start DictateAnywhere with Windows</label>
          <label className="switch">
            <input
              type="checkbox"
              id="start_with_windows"
              checked={config.start_with_windows}
              onChange={(e) => handleFieldChange("start_with_windows", e.target.checked)}
            />
            <span className="slider"></span>
          </label>
        </div>

        <div className="form-group">
          <label htmlFor="log_level">Logging Verbosity Level</label>
          <select
            id="log_level"
            value={config.log_level}
            onChange={(e) => handleFieldChange("log_level", e.target.value)}
          >
            <option value="DEBUG">DEBUG (Detailed tracing)</option>
            <option value="INFO">INFO (Standard information)</option>
            <option value="WARNING">WARNING (Only alerts/errors)</option>
            <option value="ERROR">ERROR (Fatal errors only)</option>
          </select>
        </div>
      </div>

      <div className="setting-card">
        <div className="setting-card-title">Auto-Updates</div>
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
        <div className="form-group" style={{ marginTop: "12px" }}>
          <button className="btn btn-secondary" onClick={handleCheckUpdates}>
            Check Updates Now
          </button>
          {updateCheckStatus !== "idle" && (
            <div style={{ marginTop: "8px", fontSize: "13px", color: updateCheckStatus === "error" ? "#f38ba8" : "#a6e3a1" }}>
              {updateCheckMessage}
            </div>
          )}
        </div>
      </div>

      <div className="setting-card">
        <div className="setting-card-title">Application Configuration Folder</div>
        <p style={{ fontSize: "13px", color: "#a6adc8", lineHeight: "1.4" }}>
          Open the configuration directory containing the JSON configuration files, correction database, and logs.
        </p>
        <div className="form-group" style={{ marginTop: "12px" }}>
          <button className="btn btn-secondary" onClick={handleOpenConfigFolder}>
            Open Config Folder
          </button>
        </div>
      </div>

      <div className="setting-card">
        <div className="setting-card-title">Whisper Local Model Cache</div>
        <p style={{ fontSize: "13px", color: "#a6adc8", lineHeight: "1.4", marginBottom: "12px" }}>
          These Whisper model weights are currently cached locally in your AppData directory. Deleting them frees up disk space; they will be downloaded again on next local engine launch.
        </p>
        
        {isLoadingCache ? (
           <div style={{ fontSize: "13px", color: "orange" }}>Loading cached models...</div>
        ) : cachedModels.length === 0 ? (
           <div style={{ fontSize: "13px", color: "#6c7086" }}>No local Whisper models currently cached.</div>
        ) : (
          <div className="table-container">
            <table className="settings-table">
              <thead>
                <tr>
                  <th>Model Name</th>
                  <th style={{ width: "120px" }}>Size (MB)</th>
                  <th style={{ width: "80px", textAlign: "center" }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {cachedModels.map((m) => (
                  <tr key={m.name}>
                    <td style={{ fontWeight: 600 }}>{m.name}</td>
                    <td>{m.size_mb.toFixed(0)} MB</td>
                    <td style={{ textAlign: "center" }}>
                      <button className="btn btn-danger btn-sm" onClick={() => handleDeleteModel(m.name)}>
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
};
