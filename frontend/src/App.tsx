// src/App.tsx
import { BrowserRouter, Routes, Route } from "react-router-dom";
import "./App.css";
import ClockPage from "./pages/ClockPage.js";
import ComplaintPage from "./pages/ComplaintPage.js";
import ListeningPage from "./pages/ListeningPage.js";
import SummaryPage from "./pages/SummaryPage.js";
import LogViewerPage from "./pages/LogViewerPage.js";
import LogsPage from "./pages/LogsPage.js";
import ReListeningPage from "./pages/ReListeningPage.js";
import ResultPage from "./pages/ResultPage.js";
import MessagePage from "./pages/MessagePage.js";
import SuccessPage from "./pages/SuccessPage.js";
import FinishPage from "./pages/FinishPage.js";
import PhonePage from "./pages/PhonePage.js";
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
        <Route path="/relisten" element={<ReListeningPage />} />
        <Route path="/result" element={<ResultPage />} />
        <Route path="/message" element={<MessagePage />} />
        <Route path="/success" element={<SuccessPage />} />
        <Route path="/finish" element={<FinishPage />} />
        <Route path="/phone" element={<PhonePage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
