import { useState, useCallback } from "react";
import FlowList from "./components/FlowList.jsx";
import Editor from "./components/Editor.jsx";

// Minimal state-based router: "list" screen or "editor" for a given flow.
export default function App() {
  const [view, setView] = useState({ screen: "list", flow: null });

  const openEditor = useCallback((flowName) => setView({ screen: "editor", flow: flowName }), []);
  const openList = useCallback(() => setView({ screen: "list", flow: null }), []);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand" onClick={openList} role="button" title="Home">
          <span className="logo">✈</span> FlowPilot
        </div>
        <div className="topbar-sub">Visual Desktop Automation</div>
      </header>
      {view.screen === "list" ? (
        <FlowList onOpen={openEditor} />
      ) : (
        <Editor flowName={view.flow} onBack={openList} />
      )}
    </div>
  );
}
