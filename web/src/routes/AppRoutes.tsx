import { Route, Routes } from "react-router-dom";

import { AppLayout } from "../components/layout/AppLayout";
import { DashboardPage } from "../pages/DashboardPage";
import { IntegrityPage } from "../pages/IntegrityPage";
import { LoginPage } from "../pages/LoginPage";
import { NewRecordPage } from "../pages/NewRecordPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { RecordsPage } from "../pages/RecordsPage";
import { RegisterPage } from "../pages/RegisterPage";
import { ProtectedRoute } from "./ProtectedRoute";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="records" element={<RecordsPage />} />
          <Route path="records/new" element={<NewRecordPage />} />
          <Route path="integrity" element={<IntegrityPage />} />
        </Route>
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
