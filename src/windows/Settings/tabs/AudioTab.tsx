import React from "react";

interface AudioDevice {
  index: number;
  name: string;
  channels: number;
  default_samplerate: number;
}

interface AudioTabProps {
  config: Record<string, any>;
  handleFieldChange: (field: string, val: any) => void;
  devices: AudioDevice[];
  showMicTest: boolean;
  setShowMicTest: (show: boolean) => void;
  startMicTest: () => void;
  stopMicTest: () => void;
  micLevel: number;
  micStatus: string;
  micStatusColor: string;
}

export const AudioTab: React.FC<AudioTabProps> = ({
  config,
  handleFieldChange,
  devices,
  showMicTest,
  setShowMicTest,
  startMicTest,
  stopMicTest,
  micLevel,
  micStatus,
  micStatusColor,
}) => {
  return (
    <>
      <div className="tab-title">Audio & Microphone Settings</div>
      <div className="setting-card">
        <div className="setting-card-title">Microphone Selection</div>
        <div className="form-group">
          <label htmlFor="mic_device_index">Input Device</label>
          <select
            id="mic_device_index"
            value={config.mic_device_index}
            onChange={(e) => handleFieldChange("mic_device_index", parseInt(e.target.value))}
          >
            <option value="-1">System Default Microphone</option>
            {devices.map((d) => (
              <option key={d.index} value={d.index}>
                [{d.index}] {d.name} ({d.channels} ch, {d.default_samplerate}Hz)
              </option>
            ))}
          </select>
        </div>
        <div className="form-group" style={{ marginTop: "12px" }}>
          <button
            className="btn btn-secondary"
            onClick={() => {
              setShowMicTest(true);
              startMicTest();
            }}
          >
            Test Microphone
          </button>
        </div>
      </div>

      {showMicTest && (
        <div className="modal-backdrop">
          <div className="modal-content">
            <h4>Microphone Level Meter</h4>
            <p style={{ color: "#a6adc8", fontSize: "13px" }}>Speak into your microphone to verify connection and input level.</p>
            
            <div className="mic-meter-container">
              <div className="mic-meter-bar" style={{ width: `${micLevel}%` }}></div>
            </div>
            
            <div style={{ marginTop: "12px", fontSize: "14px", fontWeight: "bold", color: micStatusColor }}>
              {micStatus}
            </div>
            
            <button
              className="btn btn-primary"
              style={{ marginTop: "20px" }}
              onClick={() => {
                stopMicTest();
                setShowMicTest(false);
              }}
            >
              Close Test
            </button>
          </div>
        </div>
      )}

      <div className="setting-card">
        <div className="setting-card-title">Voice Activity Detection (VAD)</div>
        <div className="form-group">
          <label htmlFor="vad_aggressiveness">VAD Aggressiveness</label>
          <div className="range-container">
            <input
              type="range"
              id="vad_aggressiveness"
              min="0"
              max="3"
              step="1"
              value={config.vad_aggressiveness}
              onChange={(e) => handleFieldChange("vad_aggressiveness", parseInt(e.target.value))}
            />
            <span className="range-val">{config.vad_aggressiveness}</span>
          </div>
          <div className="form-helper">
            0 = most sensitive (picks up more background noise), 3 = highly aggressive (transcribes only clear voice).
          </div>
        </div>

        <div className="grid-2">
          <div className="form-group">
            <label htmlFor="silence_timeout_ms">Silence Timeout (ms)</label>
            <input
              type="number"
              id="silence_timeout_ms"
              min="500"
              max="10000"
              step="100"
              value={config.silence_timeout_ms}
              onChange={(e) => handleFieldChange("silence_timeout_ms", parseInt(e.target.value))}
            />
            <div className="form-helper">Ms of silence before stopping dictation automatically.</div>
          </div>

          <div className="form-group">
            <label htmlFor="max_record_seconds">Max Record Duration (seconds)</label>
            <input
              type="number"
              id="max_record_seconds"
              min="5"
              max="600"
              disabled={!config.enable_max_record_limit}
              value={config.max_record_seconds}
              onChange={(e) => handleFieldChange("max_record_seconds", parseInt(e.target.value))}
            />
          </div>
        </div>

        <div className="form-group-row">
          <label htmlFor="enable_max_record_limit">Enforce Maximum Recording Limit</label>
          <label className="switch">
            <input
              type="checkbox"
              id="enable_max_record_limit"
              checked={config.enable_max_record_limit}
              onChange={(e) => handleFieldChange("enable_max_record_limit", e.target.checked)}
            />
            <span className="slider"></span>
          </label>
        </div>
      </div>
    </>
  );
};
