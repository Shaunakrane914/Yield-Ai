import { useMemo } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AboutPage } from "@/features/about/AboutPage";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { FarmSetupPage } from "@/features/farm-setup/FarmSetupPage";
import { YieldPredictionPage } from "@/features/yield-prediction/YieldPredictionPage";
import { Navbar } from "@/shared/components/Navbar";
import { hasStoredFarm } from "@/shared/lib/farmStorage";

function App() {
  const readyForDashboard = useMemo(() => hasStoredFarm(), []);

  return (
    <div className="app-shell">
      <Navbar />
      <main className="content">
        <Routes>
          <Route path="/" element={<Navigate to={readyForDashboard ? "/dashboard" : "/setup"} replace />} />
          <Route path="/setup" element={<FarmSetupPage />} />
          <Route path="/predict" element={<YieldPredictionPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
