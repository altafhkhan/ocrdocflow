import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Login from "./pages/Login";
import Register from "./pages/Register";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import Dashboard from "./pages/Dashboard";
import AdminPanel from "./pages/AdminPanel";
import VisitorPage from "./pages/VisitorPage";
import BillingPage from "./pages/BillingPage";
import TeamPage from "./pages/TeamPage";
import MobileBillingPage from "./pages/MobileBillingPage";
import { isNativeApp } from "./native";
import { getToken } from "./api";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* In the phone app, someone who is already signed in goes straight to
            their documents instead of the free-trial page. */}
        <Route
          path="/"
          element={isNativeApp && getToken() ? <Navigate to="/dashboard" replace /> : <VisitorPage />}
        />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/admin" element={<AdminPanel />} />
        {/* The apps never sell plans (no Apple/Google purchase): plans are bought on the website. */}
        <Route path="/billing" element={isNativeApp ? <MobileBillingPage /> : <BillingPage />} />
        <Route path="/team" element={<TeamPage />} />
      </Routes>
    </BrowserRouter>
  );
}


