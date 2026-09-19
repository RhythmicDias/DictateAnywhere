import React from "react";

interface CloudTabProps {
  config: Record<string, any>;
  handleFieldChange: (field: string, val: any) => void;
  geminiKey: string;
  setGeminiKey: (k: string) => void;
  showGeminiKey: boolean;
  setShowGeminiKey: (s: boolean) => void;
  testGeminiKey: () => void;
  geminiTestStatus: string;

  azureKey: string;
  setAzureKey: (k: string) => void;
  showAzureKey: boolean;
  setShowAzureKey: (s: boolean) => void;
  testAzureKey: () => void;
  azureTestStatus: string;

  sarvamKey: string;
  setSarvamKey: (k: string) => void;
  showSarvamKey: boolean;
  setShowSarvamKey: (s: boolean) => void;
  testSarvamKey: () => void;
  sarvamTestStatus: string;

  openrouterKey: string;
  setOpenRouterKey: (k: string) => void;
  showOpenRouterKey: boolean;
  setShowOpenRouterKey: (s: boolean) => void;
  testOpenRouterKey: () => void;
  openrouterTestStatus: string;

  groqKey: string;
  setGroqKey: (k: string) => void;
  showGroqKey: boolean;
  setShowGroqKey: (s: boolean) => void;
  testGroqKey: () => void;
  groqTestStatus: string;
}

export const CloudTab: React.FC<CloudTabProps> = ({
  config,
  handleFieldChange,
  geminiKey,
  setGeminiKey,
  showGeminiKey,
  setShowGeminiKey,
  testGeminiKey,
  geminiTestStatus,

  azureKey,
  setAzureKey,
  showAzureKey,
  setShowAzureKey,
  testAzureKey,
  azureTestStatus,

  sarvamKey,
  setSarvamKey,
  showSarvamKey,
  setShowSarvamKey,
  testSarvamKey,
  sarvamTestStatus,

  openrouterKey,
  setOpenRouterKey,
  showOpenRouterKey,
  setShowOpenRouterKey,
  testOpenRouterKey,
  openrouterTestStatus,

  groqKey,
  setGroqKey,
  showGroqKey,
  setShowGroqKey,
  testGroqKey,
  groqTestStatus,
}) => {
  return (
    <>
      <div className="tab-title">Cloud STT & Secure Credentials</div>

      <div className="setting-card">
        <div className="setting-card-title">Active Cloud STT Provider</div>
        <div style={{ fontSize: "12px", color: "var(--text-muted, #71717a)", marginBottom: "12px" }}>
          Select which cloud provider handles speech-to-text transcription when Cloud STT mode is enabled.
        </div>
        <div className="grid-3" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "10px" }}>
          {[
            { id: "gemini", name: "Google Gemini", desc: "Fast & Accurate (Flash)" },
            { id: "azure", name: "Microsoft Azure", desc: "Azure Cognitive Services" },
            { id: "sarvam", name: "Sarvam AI", desc: "Indian Languages" },
            { id: "openrouter", name: "OpenRouter", desc: "Multi-Model Cloud STT" },
            { id: "groq", name: "Groq Cloud", desc: "Ultra-Fast Whisper STT" },
          ].map((p) => {
            const isActive = (config.cloud_provider || config.cloud_fallback_provider || "azure") === p.id;
            return (
              <div
                key={p.id}
                onClick={() => {
                  handleFieldChange("cloud_provider", p.id);
                  handleFieldChange("cloud_fallback_provider", p.id);
                }}
                style={{
                  padding: "10px 14px",
                  borderRadius: "10px",
                  border: isActive ? "1.5px solid var(--accent-primary, #2a8f8e)" : "1px solid #e4e4e7",
                  backgroundColor: isActive ? "rgba(42, 143, 142, 0.08)" : "#ffffff",
                  cursor: "pointer",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  transition: "all 0.15s ease",
                }}
              >
                <div>
                  <div style={{ fontWeight: 600, fontSize: "13px", color: isActive ? "var(--accent-primary, #2a8f8e)" : "#18181b" }}>{p.name}</div>
                  <div style={{ fontSize: "11px", color: "#71717a" }}>{p.desc}</div>
                </div>
                <label className="switch" onClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    checked={isActive}
                    onChange={(e) => {
                      if (e.target.checked) {
                        handleFieldChange("cloud_provider", p.id);
                        handleFieldChange("cloud_fallback_provider", p.id);
                      }
                    }}
                  />
                  <span className="slider"></span>
                </label>
              </div>
            );
          })}
        </div>
      </div>

      <div className="setting-card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
          <div className="setting-card-title" style={{ margin: 0 }}>Google Gemini</div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "12px", fontWeight: 500, color: (config.cloud_provider || config.cloud_fallback_provider) === "gemini" ? "var(--accent-primary, #2a8f8e)" : "#71717a" }}>
              {(config.cloud_provider || config.cloud_fallback_provider) === "gemini" ? "Active" : "Activate"}
            </span>
            <label className="switch">
              <input
                type="checkbox"
                checked={(config.cloud_provider || config.cloud_fallback_provider) === "gemini"}
                onChange={(e) => {
                  if (e.target.checked) {
                    handleFieldChange("cloud_provider", "gemini");
                    handleFieldChange("cloud_fallback_provider", "gemini");
                  }
                }}
              />
              <span className="slider"></span>
            </label>
          </div>
        </div>
        <div className="form-group">
          <label htmlFor="gemini_key">Gemini API Key</label>
          <div className="input-with-button">
            <input
              type={showGeminiKey ? "text" : "password"}
              id="gemini_key"
              placeholder="Enter Google AI API Key..."
              value={geminiKey}
              onChange={(e) => setGeminiKey(e.target.value)}
            />
            <button className="btn btn-secondary" onClick={() => setShowGeminiKey(!showGeminiKey)}>
              {showGeminiKey ? "Hide" : "Show"}
            </button>
            <button className="btn btn-primary" onClick={testGeminiKey}>
              Test Connection
            </button>
          </div>
          {geminiTestStatus !== "idle" && (
            <div className={`connection-status ${geminiTestStatus}`}>
              {geminiTestStatus === "testing" && "Validating credentials..."}
              {geminiTestStatus === "success" && "✓ API Connection verified successfully!"}
              {geminiTestStatus === "error" && "✗ Connection failed. Check your API key."}
            </div>
          )}
        </div>

        <div className="form-group">
          <label htmlFor="gemini_stt_model">Gemini Model</label>
          <input
            type="text"
            id="gemini_stt_model"
            value={config.gemini_stt_model}
            onChange={(e) => handleFieldChange("gemini_stt_model", e.target.value)}
          />
        </div>
      </div>

      <div className="setting-card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
          <div className="setting-card-title" style={{ margin: 0 }}>Microsoft Azure Speech</div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "12px", fontWeight: 500, color: (config.cloud_provider || config.cloud_fallback_provider) === "azure" ? "var(--accent-primary, #2a8f8e)" : "#71717a" }}>
              {(config.cloud_provider || config.cloud_fallback_provider) === "azure" ? "Active" : "Activate"}
            </span>
            <label className="switch">
              <input
                type="checkbox"
                checked={(config.cloud_provider || config.cloud_fallback_provider) === "azure"}
                onChange={(e) => {
                  if (e.target.checked) {
                    handleFieldChange("cloud_provider", "azure");
                    handleFieldChange("cloud_fallback_provider", "azure");
                  }
                }}
              />
              <span className="slider"></span>
            </label>
          </div>
        </div>
        <div className="form-group">
          <label htmlFor="azure_key">Azure API Key</label>
          <div className="input-with-button">
            <input
              type={showAzureKey ? "text" : "password"}
              id="azure_key"
              placeholder="Enter Azure Speech Key..."
              value={azureKey}
              onChange={(e) => setAzureKey(e.target.value)}
            />
            <button className="btn btn-secondary" onClick={() => setShowAzureKey(!showAzureKey)}>
              {showAzureKey ? "Hide" : "Show"}
            </button>
            <button className="btn btn-primary" onClick={testAzureKey}>
              Test Connection
            </button>
          </div>
          {azureTestStatus !== "idle" && (
            <div className={`connection-status ${azureTestStatus}`}>
              {azureTestStatus === "testing" && "Validating region & key..."}
              {azureTestStatus === "success" && "✓ Key verified!"}
              {azureTestStatus === "error" && "✗ Verification failed. Check key length."}
            </div>
          )}
        </div>

        <div className="form-group">
          <label htmlFor="cloud_region">Service Region</label>
          <input
            type="text"
            id="cloud_region"
            placeholder="e.g. eastus"
            value={config.cloud_region}
            onChange={(e) => handleFieldChange("cloud_region", e.target.value)}
          />
        </div>
      </div>

      <div className="setting-card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
          <div className="setting-card-title" style={{ margin: 0 }}>Sarvam AI (Indian Languages)</div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "12px", fontWeight: 500, color: (config.cloud_provider || config.cloud_fallback_provider) === "sarvam" ? "var(--accent-primary, #2a8f8e)" : "#71717a" }}>
              {(config.cloud_provider || config.cloud_fallback_provider) === "sarvam" ? "Active" : "Activate"}
            </span>
            <label className="switch">
              <input
                type="checkbox"
                checked={(config.cloud_provider || config.cloud_fallback_provider) === "sarvam"}
                onChange={(e) => {
                  if (e.target.checked) {
                    handleFieldChange("cloud_provider", "sarvam");
                    handleFieldChange("cloud_fallback_provider", "sarvam");
                  }
                }}
              />
              <span className="slider"></span>
            </label>
          </div>
        </div>
        <div className="form-group">
          <label htmlFor="sarvam_key">Sarvam API Key</label>
          <div className="input-with-button">
            <input
              type={showSarvamKey ? "text" : "password"}
              id="sarvam_key"
              placeholder="Enter Sarvam API Key..."
              value={sarvamKey}
              onChange={(e) => setSarvamKey(e.target.value)}
            />
            <button className="btn btn-secondary" onClick={() => setShowSarvamKey(!showSarvamKey)}>
              {showSarvamKey ? "Hide" : "Show"}
            </button>
            <button className="btn btn-primary" onClick={testSarvamKey}>
              Test Connection
            </button>
          </div>
          {sarvamTestStatus !== "idle" && (
            <div className={`connection-status ${sarvamTestStatus}`}>
              {sarvamTestStatus === "testing" && "Checking connection..."}
              {sarvamTestStatus === "success" && "✓ Connection verified!"}
              {sarvamTestStatus === "error" && "✗ Verification failed."}
            </div>
          )}
        </div>

        <div className="grid-2">
          <div className="form-group">
            <label htmlFor="sarvam_model">Sarvam Model</label>
            <select
              id="sarvam_model"
              value={config.sarvam_model}
              onChange={(e) => handleFieldChange("sarvam_model", e.target.value)}
            >
              <option value="saarika:v2.5">Saarika v2.5 (Fast)</option>
              <option value="saaras:v3">Saaras v3 (Premium)</option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="sarvam_language">Primary Language</label>
            <select
              id="sarvam_language"
              value={config.sarvam_language}
              onChange={(e) => handleFieldChange("sarvam_language", e.target.value)}
            >
              <option value="hi-IN">Hindi (hi-IN)</option>
              <option value="ta-IN">Tamil (ta-IN)</option>
              <option value="te-IN">Telugu (te-IN)</option>
              <option value="kn-IN">Kannada (kn-IN)</option>
              <option value="ml-IN">Malayalam (ml-IN)</option>
              <option value="mr-IN">Marathi (mr-IN)</option>
              <option value="bn-IN">Bengali (bn-IN)</option>
              <option value="gu-IN">Gujarati (gu-IN)</option>
            </select>
          </div>
        </div>

        <div className="form-group-row">
          <label htmlFor="enable_sarvam_websocket">Enable WebSocket Real-Time STT</label>
          <label className="switch">
            <input
              type="checkbox"
              id="enable_sarvam_websocket"
              checked={config.enable_sarvam_websocket}
              onChange={(e) => handleFieldChange("enable_sarvam_websocket", e.target.checked)}
            />
            <span className="slider"></span>
          </label>
        </div>
      </div>

      <div className="setting-card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
          <div className="setting-card-title" style={{ margin: 0 }}>OpenRouter</div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "12px", fontWeight: 500, color: (config.cloud_provider || config.cloud_fallback_provider) === "openrouter" ? "var(--accent-primary, #2a8f8e)" : "#71717a" }}>
              {(config.cloud_provider || config.cloud_fallback_provider) === "openrouter" ? "Active" : "Activate"}
            </span>
            <label className="switch">
              <input
                type="checkbox"
                checked={(config.cloud_provider || config.cloud_fallback_provider) === "openrouter"}
                onChange={(e) => {
                  if (e.target.checked) {
                    handleFieldChange("cloud_provider", "openrouter");
                    handleFieldChange("cloud_fallback_provider", "openrouter");
                  }
                }}
              />
              <span className="slider"></span>
            </label>
          </div>
        </div>
        <div className="form-group">
          <label htmlFor="openrouter_key">OpenRouter API Key</label>
          <div className="input-with-button">
            <input
              type={showOpenRouterKey ? "text" : "password"}
              id="openrouter_key"
              placeholder="Enter OpenRouter API Key..."
              value={openrouterKey}
              onChange={(e) => setOpenRouterKey(e.target.value)}
            />
            <button className="btn btn-secondary" onClick={() => setShowOpenRouterKey(!showOpenRouterKey)}>
              {showOpenRouterKey ? "Hide" : "Show"}
            </button>
            <button className="btn btn-primary" onClick={testOpenRouterKey}>
              Test Connection
            </button>
          </div>
          {openrouterTestStatus !== "idle" && (
            <div className={`connection-status ${openrouterTestStatus}`}>
              {openrouterTestStatus === "testing" && "Checking connection..."}
              {openrouterTestStatus === "success" && "✓ Connection verified!"}
              {openrouterTestStatus === "error" && "✗ Verification failed."}
            </div>
          )}
        </div>

        <div className="form-group">
          <label htmlFor="openrouter_stt_model">OpenRouter Model</label>
          <input
            type="text"
            id="openrouter_stt_model"
            placeholder="openai/whisper-1"
            value={config.openrouter_stt_model || ""}
            onChange={(e) => handleFieldChange("openrouter_stt_model", e.target.value)}
          />
        </div>
      </div>

      <div className="setting-card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
          <div className="setting-card-title" style={{ margin: 0 }}>Groq Cloud</div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "12px", fontWeight: 500, color: (config.cloud_provider || config.cloud_fallback_provider) === "groq" ? "var(--accent-primary, #2a8f8e)" : "#71717a" }}>
              {(config.cloud_provider || config.cloud_fallback_provider) === "groq" ? "Active" : "Activate"}
            </span>
            <label className="switch">
              <input
                type="checkbox"
                checked={(config.cloud_provider || config.cloud_fallback_provider) === "groq"}
                onChange={(e) => {
                  if (e.target.checked) {
                    handleFieldChange("cloud_provider", "groq");
                    handleFieldChange("cloud_fallback_provider", "groq");
                  }
                }}
              />
              <span className="slider"></span>
            </label>
          </div>
        </div>
        <div className="form-group">
          <label htmlFor="groq_key">Groq API Key</label>
          <div className="input-with-button">
            <input
              type={showGroqKey ? "text" : "password"}
              id="groq_key"
              placeholder="Enter Groq API Key..."
              value={groqKey}
              onChange={(e) => setGroqKey(e.target.value)}
            />
            <button className="btn btn-secondary" onClick={() => setShowGroqKey(!showGroqKey)}>
              {showGroqKey ? "Hide" : "Show"}
            </button>
            <button className="btn btn-primary" onClick={testGroqKey}>
              Test Connection
            </button>
          </div>
          {groqTestStatus !== "idle" && (
            <div className={`connection-status ${groqTestStatus}`}>
              {groqTestStatus === "testing" && "Checking connection..."}
              {groqTestStatus === "success" && "✓ Connection verified!"}
              {groqTestStatus === "error" && "✗ Verification failed."}
            </div>
          )}
        </div>

        <div className="form-group">
          <label htmlFor="groq_stt_model">Groq Model</label>
          <input
            type="text"
            id="groq_stt_model"
            placeholder="whisper-large-v3-turbo"
            value={config.groq_stt_model || ""}
            onChange={(e) => handleFieldChange("groq_stt_model", e.target.value)}
          />
        </div>
      </div>
    </>
  );
};
