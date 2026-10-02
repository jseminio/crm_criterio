import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { Entrada } from "./entrada";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Entrada>
      <App />
    </Entrada>
  </StrictMode>,
);
