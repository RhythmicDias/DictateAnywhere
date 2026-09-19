import React from "react";

interface EngineTabProps {
  config: Record<string, any>;
  handleFieldChange: (field: string, val: any) => void;
}

export const EngineTab: React.FC<EngineTabProps> = ({ config, handleFieldChange }) => {
  return (
    <>
      <div className="tab-title">Engine Configuration</div>
      <div className="setting-card">
        <div className="setting-card-title">Transcription Engine</div>
        <div className="form-group">
          <label htmlFor="engine_mode">Engine Mode</label>
          <select
            id="engine_mode"
            value={config.engine_mode}
            onChange={(e) => handleFieldChange("engine_mode", e.target.value)}
          >
            <option value="local">Local (Whisper GPU/CPU)</option>
            <option value="cloud">Cloud (Azure/Gemini/Sarvam/Groq/OpenRouter)</option>
            <option value="hybrid">Hybrid (Local with Cloud Fallback)</option>
          </select>
          <div className="form-helper">
            Select how dictation is processed. Hybrid attempts local first and falls back to cloud on failure.
          </div>
        </div>

        <div className="form-group-row">
          <label htmlFor="cloud_fallback_on_error">Enable Cloud Fallback on Error</label>
          <label className="switch">
            <input
              type="checkbox"
              id="cloud_fallback_on_error"
              checked={config.cloud_fallback_on_error}
              onChange={(e) => handleFieldChange("cloud_fallback_on_error", e.target.checked)}
            />
            <span className="slider"></span>
          </label>
        </div>

        <div className="form-group-row">
          <label htmlFor="local_fallback_on_cloud_error">Enable Local Fallback on Cloud Error</label>
          <label className="switch">
            <input
              type="checkbox"
              id="local_fallback_on_cloud_error"
              checked={config.local_fallback_on_cloud_error}
              onChange={(e) => handleFieldChange("local_fallback_on_cloud_error", e.target.checked)}
            />
            <span className="slider"></span>
          </label>
        </div>

        {config.cloud_fallback_on_error && (
          <div className="form-group">
            <label htmlFor="cloud_fallback_provider">Cloud Fallback Provider</label>
            <select
              id="cloud_fallback_provider"
              value={config.cloud_fallback_provider}
              onChange={(e) => handleFieldChange("cloud_fallback_provider", e.target.value)}
            >
              <option value="azure">Azure Speech Services</option>
              <option value="gemini">Google Gemini Flash</option>
              <option value="sarvam">Sarvam AI (Indian Languages)</option>
              <option value="groq">Groq Cloud (Ultra-Fast Whisper)</option>
              <option value="openrouter">OpenRouter (Multi-Model STT)</option>
            </select>
          </div>
        )}
      </div>

      <div className="setting-card">
        <div className="setting-card-title">Local Whisper Settings</div>
        <div className="grid-2">
          <div className="form-group">
            <label htmlFor="model_size">Model Size</label>
            <select
              id="model_size"
              value={config.model_size}
              onChange={(e) => handleFieldChange("model_size", e.target.value)}
            >
              <option value="tiny">Tiny (Fastest, low VRAM)</option>
              <option value="base">Base</option>
              <option value="small">Small (Recommended default)</option>
              <option value="medium">Medium</option>
              <option value="large-v2">Large V2</option>
              <option value="large-v3">Large V3 (Most accurate, high VRAM)</option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="compute_type">Compute Type</label>
            <select
              id="compute_type"
              value={config.compute_type}
              onChange={(e) => handleFieldChange("compute_type", e.target.value)}
            >
              <option value="int8">int8 (Lightweight, low VRAM)</option>
              <option value="float16">float16 (Fastest on GPU)</option>
              <option value="float32">float32</option>
              <option value="int8_float16">int8_float16</option>
            </select>
          </div>
        </div>

        <div className="grid-2">
          <div className="form-group">
            <label htmlFor="local_device">Hardware Device</label>
            <select
              id="local_device"
              value={config.local_device}
              onChange={(e) => handleFieldChange("local_device", e.target.value)}
            >
              <option value="auto">Auto-detect</option>
              <option value="cuda">NVIDIA CUDA GPU</option>
              <option value="cpu">CPU (Slow)</option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="language">Target Language</label>
            <select
              id="language"
              value={config.language}
              onChange={(e) => handleFieldChange("language", e.target.value)}
            >
              <option value="auto">Auto-detect Language</option>
              <option value="en">English (en)</option>
              <option value="es">Spanish (es)</option>
              <option value="fr">French (fr)</option>
              <option value="de">German (de)</option>
              <option value="it">Italian (it)</option>
              <option value="ja">Japanese (ja)</option>
              <option value="zh">Chinese (zh)</option>
              <option value="pt">Portuguese (pt)</option>
              <option value="hi">Hindi (hi)</option>
              <option value="nl">Dutch (nl)</option>
              <option value="pl">Polish (pl)</option>
              <option value="ru">Russian (ru)</option>
              <option value="ko">Korean (ko)</option>
              <option value="ar">Arabic (ar)</option>
            </select>
          </div>
        </div>
      </div>
    </>
  );
};
