import { BrowserRouter, Routes, Route } from "react-router-dom";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import AdminPanel from "./pages/AdminPanel";
import VisitorPage from "./pages/VisitorPage";
import BillingPage from "./pages/BillingPage";
import TeamPage from "./pages/TeamPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<VisitorPage />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/admin" element={<AdminPanel />} />
        <Route path="/billing" element={<BillingPage />} />
        <Route path="/team" element={<TeamPage />} />
      </Routes>
    </BrowserRouter>
  );
}


