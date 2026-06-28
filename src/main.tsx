import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

// Disable default browser context menu (Right-click menu) globally.
// This prevents Webview2 default menus (Refresh, Inspect, etc.) from showing.
if (import.meta.env.PROD) {
  document.addEventListener("contextmenu", (e) => e.preventDefault());
} else {
  // If you want to disable it in dev too, uncomment below:
  document.addEventListener("contextmenu", (e) => {
    // Only allow context menu if target is inside an element we want to debug, 
    // or disable completely to resemble production behavior:
    e.preventDefault();
  });
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

