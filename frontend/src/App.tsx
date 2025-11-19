// src/App.tsx
import { BrowserRouter, Routes, Route } from "react-router-dom";
import TestPage from "../src/pages/TestPage.js";
import "./App.css";
import ClockPage from "./pages/ClockPage.js";
import ComplaintPage from "./pages/ComplaintPage.js";
import ListeningPage from "./pages/ListeningPage.js";
import SummaryPage from "./pages/SummaryPage.js";
import LogViewerPage from "./pages/LogViewerPage.js";
import LogsPage from "./pages/LogsPage.js";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ClockPage />} />
        <Route path="/complaint" element={<ComplaintPage />} />
        <Route path="/listen" element={<ListeningPage />} />
        <Route path="/summary" element={<SummaryPage />} />
        <Route path="/logs" element={<LogViewerPage />} />
        <Route path="/logstest" element={<LogsPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
