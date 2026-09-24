import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { ToastHost } from "./components/ui";
import { AuthProvider } from "./lib/auth";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>
);

const toastRoot = document.getElementById("toast-root");
if (toastRoot) {
  ReactDOM.createRoot(toastRoot).render(
    <React.StrictMode>
      <ToastHost />
    </React.StrictMode>
  );
}
