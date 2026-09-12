import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";
import { applyStoredMotionPreference } from "./lib/motionPreference";

applyStoredMotionPreference(); // before first paint — avoids a flash of full motion, then a snap to reduced

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
