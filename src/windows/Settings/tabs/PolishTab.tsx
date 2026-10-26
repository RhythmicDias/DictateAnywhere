import React from "react";

const TRANSLATION_LANGUAGES = [
  "Afrikaans",
  "Albanian",
  "Amharic",
  "Arabic",
  "Armenian",
  "Assamese",
  "Azerbaijani",
  "Basque",
  "Belarusian",
  "Bengali",
  "Bosnian",
  "Bulgarian",
  "Burmese",
  "Catalan",
  "Cebuano",
  "Chinese (Simplified)",
  "Chinese (Traditional)",
  "Croatian",
  "Czech",
  "Danish",
  "Dutch",
  "English",
  "Esperanto",
  "Estonian",
  "Filipino (Tagalog)",
  "Finnish",
  "French",
  "Galician",
  "Georgian",
  "German",
  "Greek",
  "Gujarati",
  "Haitian Creole",
  "Hausa",
  "Hebrew",
  "Hindi",
  "Hungarian",
  "Icelandic",
  "Igbo",
  "Indonesian",
  "Irish",
  "Italian",
  "Japanese",
  "Javanese",
  "Kannada",
  "Kazakh",
  "Khmer",
  "Kinyarwanda",
  "Konkani",
  "Korean",
  "Kurdish",
  "Kyrgyz",
  "Lao",
  "Latin",
  "Latvian",
  "Lithuanian",
  "Luxembourgish",
  "Macedonian",
  "Maithili",
  "Malagasy",
  "Malay",
  "Malayalam",
  "Maltese",
  "Manipuri",
  "Maori",
  "Marathi",
  "Mongolian",
  "Nepali",
  "Norwegian",
  "Odia (Oriya)",
  "Pashto",
  "Persian (Farsi)",
  "Polish",
  "Portuguese",
  "Punjabi",
  "Romanian",
  "Russian",
  "Sanskrit",
  "Santali",
  "Scots Gaelic",
  "Serbian",
  "Sindhi",
  "Sinhala",
  "Slovak",
  "Slovenian",
  "Somali",
  "Spanish",
  "Sundanese",
  "Swahili",
  "Swedish",
  "Tajik",
  "Tamil",
  "Tatar",
  "Telugu",
  "Thai",
  "Tibetan",
  "Turkish",
  "Turkmen",
  "Ukrainian",
  "Urdu",
  "Uyghur",
  "Uzbek",
  "Vietnamese",
  "Welsh",
  "Xhosa",
  "Yiddish",
  "Yoruba",
  "Zulu",
];

const TRANSLATION_SCRIPTS = [
  "Default (Native Script)",
  "Latin / Romanized (Transliterated)",
  "Arabic / Perso-Arabic",
  "Armenian",
  "Assamese",
  "Bengali",
  "Burmese (Myanmar)",
  "Chinese (Simplified Han)",
  "Chinese (Traditional Han)",
  "Cyrillic",
  "Devanagari (Hindi / Marathi / Sanskrit)",
  "Ethiopic (Ge'ez)",
  "Georgian",
  "Greek",
  "Gujarati",
  "Gurmukhi (Punjabi)",
  "Hangul (Korean)",
  "Hebrew",
  "Japanese (Kanji / Kana)",
  "Kannada",
  "Khmer",
  "Lao",
  "Malayalam",
  "Meitei Mayek (Manipuri)",
  "Mongolian",
  "Odia (Oriya)",
  "Ol Chiki (Santali)",
  "Sinhala",
  "Tamil",
  "Telugu",
  "Thaana (Dhivehi)",
  "Thai",
  "Tibetan",
  "Urdu (Nastaliq)",
];

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

        {(config.enable_polish || config.enable_translation) && (
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

              {config.enable_polish && (
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
              )}
            </div>

            {config.enable_polish && config.polish_action === "Custom Prompt" && (
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

      <div className="setting-card">
        <div className="setting-card-title">Translation</div>
        <div className="form-group-row">
          <label htmlFor="enable_translation">Enable Translation</label>
          <label className="switch">
            <input
              type="checkbox"
              id="enable_translation"
              checked={!!config.enable_translation}
              onChange={(e) => handleFieldChange("enable_translation", e.target.checked)}
            />
            <span className="slider"></span>
          </label>
        </div>

        {config.enable_translation && (
          <>
            <div className="grid-2">
              <div className="form-group">
                <label htmlFor="translation_language">Target Language</label>
                <select
                  id="translation_language"
                  value={config.translation_language || "English"}
                  onChange={(e) => handleFieldChange("translation_language", e.target.value)}
                >
                  {TRANSLATION_LANGUAGES.map((lang) => (
                    <option key={lang} value={lang}>
                      {lang}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="translation_script">Translation Language Script</label>
                <select
                  id="translation_script"
                  value={config.translation_script || "Default (Native Script)"}
                  onChange={(e) => handleFieldChange("translation_script", e.target.value)}
                >
                  {TRANSLATION_SCRIPTS.map((script) => (
                    <option key={script} value={script}>
                      {script}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="form-helper" style={{ paddingBottom: "6px" }}>
              Transcribed text is sent to the selected Polish Provider and returned in the target language and script (e.g. Konkani in Kannada script).
            </div>
          </>
        )}
      </div>
    </>
  );
};
