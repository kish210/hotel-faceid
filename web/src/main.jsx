import React from "react";
import { createRoot } from "react-dom/client";
import { HashRouter, Navigate, Route, Routes } from "react-router-dom";

import App from "./App.jsx";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Guests from "./pages/Guests.jsx";
import PersonDetail from "./pages/PersonDetail.jsx";
import Cameras from "./pages/Cameras.jsx";
import Reports from "./pages/Reports.jsx";
import FaceSearch from "./pages/FaceSearch.jsx";
import Users from "./pages/Users.jsx";
import Audit from "./pages/Audit.jsx";
import { getToken } from "./api.js";
import { TooltipProvider } from "@/components/ui/tooltip";
import "./globals.css";

function Protected({ children }) {
  return getToken() ? children : <Navigate to="/login" replace />;
}

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <HashRouter>
      <TooltipProvider>
        <div className="dark min-h-screen">
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route
              path="/"
              element={
                <Protected>
                  <App />
                </Protected>
              }
            >
              <Route index element={<Dashboard />} />
              <Route path="guests" element={<Guests />} />
              <Route path="persons/:id" element={<PersonDetail />} />
              <Route path="cameras" element={<Cameras />} />
              <Route path="reports" element={<Reports />} />
              <Route path="face-search" element={<FaceSearch />} />
              <Route path="users" element={<Users />} />
              <Route path="audit" element={<Audit />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </TooltipProvider>
    </HashRouter>
  </React.StrictMode>
);
