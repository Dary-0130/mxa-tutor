import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { cleanupExpiredOverviewSeen } from "./lib/localStore";
import "./styles/index.css";

cleanupExpiredOverviewSeen();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
