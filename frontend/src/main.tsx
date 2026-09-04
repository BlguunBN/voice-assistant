import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import OverlayApp from "./OverlayApp";
import "./styles.css";

const page = window.location.pathname === "/overlay" ? <OverlayApp /> : <App />;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {page}
  </StrictMode>,
);
