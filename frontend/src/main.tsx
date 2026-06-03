import React from "react";
import ReactDOM from "react-dom/client";
import { Provider } from "react-redux";
import App from "./App";
import { idstore } from "./redux/IDStore";
import { I18nProvider } from "./i18n/I18nProvider";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <I18nProvider>
      <Provider store={idstore}>
        <App />
      </Provider>
    </I18nProvider>
  </React.StrictMode>
);
