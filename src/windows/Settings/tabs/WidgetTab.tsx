import React from "react";

interface WidgetTabProps {
  config: Record<string, any>;
  handleFieldChange: (field: string, val: any) => void;
}

export const WidgetTab: React.FC<WidgetTabProps> = ({ config, handleFieldChange }) => {
  return (
    <>
      <div className="tab-title">Floating Widget Settings</div>
      <div className="setting-card">
        <div className="setting-card-title">Widget Appearance</div>
        <div className="form-group-row">
          <label htmlFor="show_floating_widget">Enable Floating Widget</label>
          <label className="switch">
            <input
              type="checkbox"
              id="show_floating_widget"
              checked={config.show_floating_widget}
              onChange={(e) => handleFieldChange("show_floating_widget", e.target.checked)}
            />
            <span className="slider"></span>
          </label>
        </div>

        <div className="form-group-row">
          <label htmlFor="widget_always_on_top">Keep Widget Always on Top</label>
          <label className="switch">
            <input
              type="checkbox"
              id="widget_always_on_top"
              checked={config.widget_always_on_top}
              onChange={(e) => handleFieldChange("widget_always_on_top", e.target.checked)}
            />
            <span className="slider"></span>
          </label>
        </div>

        <div className="form-group">
          <label htmlFor="widget_size">Widget Diameter (px)</label>
          <div className="range-container">
            <input
              type="range"
              id="widget_size"
              min="32"
              max="128"
              step="4"
              value={config.widget_size}
              onChange={(e) => handleFieldChange("widget_size", parseInt(e.target.value))}
            />
            <span className="range-val">{config.widget_size}px</span>
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="widget_opacity">Widget Idle Opacity</label>
          <div className="range-container">
            <input
              type="range"
              id="widget_opacity"
              min="0.1"
              max="1.0"
              step="0.05"
              value={config.widget_opacity}
              onChange={(e) => handleFieldChange("widget_opacity", parseFloat(e.target.value))}
            />
            <span className="range-val">{Math.round(config.widget_opacity * 100)}%</span>
          </div>
        </div>
      </div>
    </>
  );
};
