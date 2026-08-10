import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { DiscussScreen } from "./screens/DiscussScreen";

const root = document.getElementById("root");
if (!root) throw new Error("Root element not found");

createRoot(root).render(
  <StrictMode>
    <DiscussScreen
      sessionId={crypto.randomUUID().slice(0, 8)}
      serverUrl="ws://localhost:8000"
    />
  </StrictMode>,
);
