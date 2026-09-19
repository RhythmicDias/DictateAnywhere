import React from "react";

interface CorrectionPair {
  from: string;
  to: string;
}

interface CorrectionsTabProps {
  corrections: CorrectionPair[];
  newFromWord: string;
  setNewFromWord: (val: string) => void;
  newToWord: string;
  setNewToWord: (val: string) => void;
  addCorrection: () => void;
  updateCorrectionField: (index: number, field: "from" | "to", value: string) => void;
  removeCorrection: (index: number) => void;
}

export const CorrectionsTab: React.FC<CorrectionsTabProps> = ({
  corrections,
  newFromWord,
  setNewFromWord,
  newToWord,
  setNewToWord,
  addCorrection,
  updateCorrectionField,
  removeCorrection,
}) => {
  return (
    <>
      <div className="tab-title">Word Corrections & Replacements</div>
      <div className="setting-card">
        <div className="setting-card-title">Define Word Corrections</div>
        <p style={{ fontSize: "12px", color: "var(--text-muted, #71717a)", lineHeight: "1.4", marginBottom: "8px" }}>
          Define case-insensitive text replacements applied to the transcribed text. Match boundaries automatically enforce whole-word searches.
        </p>

        {/* Add new correction */}
        <div className="grid-2">
          <div className="form-group">
            <label>Spoken Word / Pattern (from)</label>
            <input
              type="text"
              placeholder="e.g. teh"
              value={newFromWord}
              onChange={(e) => setNewFromWord(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label>Replacement Text (to)</label>
            <div className="input-with-button">
              <input
                type="text"
                placeholder="e.g. the"
                value={newToWord}
                onChange={(e) => setNewToWord(e.target.value)}
              />
              <button className="btn btn-primary" onClick={addCorrection}>
                Add Pair
              </button>
            </div>
          </div>
        </div>

        {/* List table */}
        <div className="table-container">
          <table className="settings-table">
            <thead>
              <tr>
                <th>Spoken Phrase (Case Insensitive)</th>
                <th>Verbatim Replacement</th>
                <th style={{ width: "80px", textAlign: "center" }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {corrections.length === 0 ? (
                <tr>
                  <td colSpan={3} style={{ textAlign: "center", color: "#6c7086", padding: "16px" }}>
                    No word corrections defined yet.
                  </td>
                </tr>
              ) : (
                corrections.map((corr, idx) => (
                  <tr key={idx}>
                    <td>
                      <input
                        type="text"
                        className="table-input"
                        value={corr.from}
                        onChange={(e) => updateCorrectionField(idx, "from", e.target.value)}
                      />
                    </td>
                    <td>
                      <input
                        type="text"
                        className="table-input"
                        value={corr.to}
                        onChange={(e) => updateCorrectionField(idx, "to", e.target.value)}
                      />
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <button className="btn btn-danger btn-sm" onClick={() => removeCorrection(idx)}>
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
