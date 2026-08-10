import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

const root = document.getElementById("root");
if (!root) throw new Error("Root element not found");

createRoot(root).render(
  <StrictMode>
    <div style={{ fontFamily: "system-ui, sans-serif", padding: "2rem" }}>
      <h1>Atlas Flow</h1>
      <p>Provider-agnostic orchestration runtime.</p>
    </div>
  </StrictMode>,
);
