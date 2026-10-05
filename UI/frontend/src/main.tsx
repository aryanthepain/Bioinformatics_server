import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles/tokens.css";
import "./styles/global.css";
import "./styles/ui.css";

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error('Could not find the <div id="root"> element in index.html.');
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
