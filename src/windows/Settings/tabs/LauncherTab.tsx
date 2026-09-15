import React from "react";

interface LauncherTabProps {
  config: Record<string, any>;
  newCommandText: string;
  setNewCommandText: (val: string) => void;
  newCommandPath: string;
  setNewCommandPath: (val: string) => void;
  handleLauncherBrowse: () => void;
  addLauncherCommand: () => void;
  removeLauncherCommand: (cmd: string) => void;
}

export const LauncherTab: React.FC<LauncherTabProps> = ({
  config,
  newCommandText,
  setNewCommandText,
  newCommandPath,
  setNewCommandPath,
  handleLauncherBrowse,
  addLauncherCommand,
  removeLauncherCommand,
}) => {
  return (
    <>
      <div className="tab-title">App Launcher Voice Commands</div>
      <div className="setting-card">
        <div className="setting-card-title">Voice Command Mappings</div>
        <p style={{ fontSize: "13px", color: "#a6adc8", lineHeight: "1.4" }}>
          Map specific spoken phrases to trigger opening local executables, files, folders or command scripts.
        </p>

        {/* Add new Launcher command */}
        <div className="grid-2">
          <div className="form-group">
            <label>Spoken Phrase</label>
            <input
              type="text"
              placeholder="e.g. open notepad"
              value={newCommandText}
              onChange={(e) => setNewCommandText(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label>Executable / File path</label>
            <div className="input-with-button">
              <input
                type="text"
                placeholder="e.g. C:\Windows\notepad.exe"
                value={newCommandPath}
                onChange={(e) => setNewCommandPath(e.target.value)}
              />
              <button className="btn btn-secondary" onClick={handleLauncherBrowse}>
                Browse...
              </button>
              <button className="btn btn-primary" onClick={addLauncherCommand}>
                Add Mapped Path
              </button>
            </div>
          </div>
        </div>

        {/* Mappings table */}
        <div className="table-container">
          <table className="settings-table">
            <thead>
              <tr>
                <th>Spoken Voice Command</th>
                <th>Target File / Folder / Program Path</th>
                <th style={{ width: "80px", textAlign: "center" }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {!config.app_launcher_commands || Object.keys(config.app_launcher_commands).length === 0 ? (
                <tr>
                  <td colSpan={3} style={{ textAlign: "center", color: "#6c7086", padding: "16px" }}>
                    No launcher commands configured.
                  </td>
                </tr>
              ) : (
                Object.entries(config.app_launcher_commands).map(([cmd, path]) => (
                  <tr key={cmd}>
                    <td style={{ fontWeight: 600, color: "#f9e2af" }}>{cmd}</td>
                    <td style={{ fontFamily: "monospace", fontSize: "12px", color: "#a6adc8", wordBreak: "break-all" }}>
                      {path as string}
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <button className="btn btn-danger btn-sm" onClick={() => removeLauncherCommand(cmd)}>
                        Delete
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
};
