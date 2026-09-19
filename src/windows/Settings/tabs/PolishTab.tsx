import React from "react";

interface PolishTabProps {
  config: Record<string, any>;
  handleFieldChange: (field: string, val: any) => void;
  fetchOllamaModels: (url: string) => void;
  ollamaStatus: "idle" | "loading" | "success" | "error";
  ollamaError: string;
  ollamaModels: string[];
}

export const PolishTab: React.FC<PolishTabProps> = ({
  config,
  handleFieldChange,
  fetchOllamaModels,
  ollamaStatus,
  ollamaError,
  ollamaModels,
}) => {
  return (
    <>
      <div className="tab-title">LLM Transcription Polish</div>
      <div className="setting-card">
        <div className="setting-card-title">Configure Text Polishing</div>
        <div className="form-group-row">
          <label htmlFor="enable_polish">Enable Text Polishing (LLM Refinement)</label>
          <label className="switch">
            <input
              type="checkbox"
              id="enable_polish"
              checked={config.enable_polish}
              onChange={(e) => handleFieldChange("enable_polish", e.target.checked)}
            />
            <span className="slider"></span>
          </label>
        </div>

        {config.enable_polish && (
          <>
            <div className="grid-2">
              <div className="form-group">
                <label htmlFor="polish_provider">Polish Provider</label>
                <select
                  id="polish_provider"
                  value={config.polish_provider}
                  onChange={(e) => handleFieldChange("polish_provider", e.target.value)}
                >
                  <option value="ollama">Ollama (Local LLM)</option>
                  <option value="gemini">Google Gemini AI</option>
                  <option value="openrouter">OpenRouter AI</option>
                  <option value="groq">Groq API</option>
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="polish_action">Refinement Action</label>
                <select
                  id="polish_action"
                  value={config.polish_action}
                  onChange={(e) => handleFieldChange("polish_action", e.target.value)}
                >
                  <option value="Fix Grammar & Spelling">Fix Grammar & Spelling</option>
                  <option value="Make Professional">Make Professional</option>
                  <option value="Summarize">Summarize</option>
                  <option value="Bullet Points">Create Bullet Points</option>
                  <option value="Chat">Chat</option>
                  <option value="Custom Prompt">Use Custom Prompt</option>
                </select>
              </div>
            </div>

            {config.polish_action === "Custom Prompt" && (
              <div className="form-group">
                <label htmlFor="custom_polish_prompt">Custom Polish Prompt</label>
                <textarea
                  id="custom_polish_prompt"
                  rows={3}
                  value={config.custom_polish_prompt}
                  onChange={(e) => handleFieldChange("custom_polish_prompt", e.target.value)}
                />
              </div>
            )}

            {config.polish_provider === "ollama" ? (
              <>
                <div className="grid-2">
                  <div className="form-group">
                    <label htmlFor="ollama_url">Ollama API URL</label>
                    <div className="input-with-button">
                      <input
                        type="text"
                        id="ollama_url"
                        value={config.ollama_url}
                        onChange={(e) => handleFieldChange("ollama_url", e.target.value)}
                      />
                      <button
                        className="btn btn-secondary"
                        onClick={() => fetchOllamaModels(config.ollama_url)}
                      >
                        Refresh
                      </button>
                    </div>
                  </div>

                  <div className="form-group">
                    <label htmlFor="polish_ollama_model">Ollama Model</label>
                    {ollamaStatus === "loading" && <div style={{ fontSize: "11px", color: "orange" }}>Fetching local models...</div>}
                    {ollamaStatus === "error" && (
                      <div style={{ fontSize: "11px", color: "#f38ba8", marginBottom: "4px" }}>
                        {ollamaError || "Connection offline. Using manual input fallback."}
                      </div>
                    )}
                    {ollamaStatus === "error" || ollamaModels.length === 0 ? (
                      <input
                        type="text"
                        id="polish_ollama_model"
                        placeholder="e.g. llama3"
                        value={config.polish_ollama_model}
                        onChange={(e) => handleFieldChange("polish_ollama_model", e.target.value)}
                      />
                    ) : (
                      <select
                        id="polish_ollama_model"
                        value={config.polish_ollama_model}
                        onChange={(e) => handleFieldChange("polish_ollama_model", e.target.value)}
                      >
                        {!ollamaModels.includes(config.polish_ollama_model) && config.polish_ollama_model && (
                          <option value={config.polish_ollama_model}>
                            {config.polish_ollama_model}
                          </option>
                        )}
                        {ollamaModels.map((m) => (
                          <option key={m} value={m}>
                            {m}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                </div>
                <div className="form-group" style={{ marginTop: "12px" }}>
                  <label htmlFor="polish_ollama_timeout">Ollama Timeout (seconds)</label>
                  <div className="range-container">
                    <input
                      type="range"
                      id="polish_ollama_timeout"
                      min="10"
                      max="300"
                      step="5"
                      value={config.polish_ollama_timeout ?? 90}
                      onChange={(e) => handleFieldChange("polish_ollama_timeout", parseInt(e.target.value))}
                    />
                    <span className="range-val">{config.polish_ollama_timeout ?? 90}s</span>
                  </div>
                </div>
              </>
            ) : config.polish_provider === "gemini" ? (
              <div className="form-group">
                <label htmlFor="polish_gemini_model">Gemini Model</label>
                <input
                  type="text"
                  id="polish_gemini_model"
                  value={config.polish_gemini_model}
                  onChange={(e) => handleFieldChange("polish_gemini_model", e.target.value)}
                />
              </div>
            ) : config.polish_provider === "openrouter" ? (
              <div className="form-group">
                <label htmlFor="polish_openrouter_model">OpenRouter Model</label>
                <input
                  type="text"
                  id="polish_openrouter_model"
                  placeholder="Enter OpenRouter Model Name (e.g. google/gemini-2.5-flash)"
                  value={config.polish_openrouter_model}
                  onChange={(e) => handleFieldChange("polish_openrouter_model", e.target.value)}
                />
              </div>
            ) : config.polish_provider === "groq" ? (
              <div className="form-group">
                <label htmlFor="polish_groq_model">Groq Model</label>
                <input
                  type="text"
                  id="polish_groq_model"
                  placeholder="Enter Groq Model Name (e.g. llama-3.3-70b-versatile)"
                  value={config.polish_groq_model}
                  onChange={(e) => handleFieldChange("polish_groq_model", e.target.value)}
                />
              </div>
            ) : null}
          </>
        )}
      </div>
    </>
  );
};
