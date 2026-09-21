/**
 * Root Application Router & Context Wrapper
 */

import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { MonitoringProvider } from './context/MonitoringContext';
import { AppLayout } from './components/layout/AppLayout';
import { Login } from './pages/Login';
import { ControlRoom } from './pages/ControlRoom';
import { JointPassport } from './pages/JointPassport';
import { SensorAnalytics } from './pages/SensorAnalytics';
import { AIDiagnosis } from './pages/AIDiagnosis';
import { Alerts } from './pages/Alerts';
import { SettingsPage } from './pages/Settings';

// Route guard component
const ProtectedLayout: React.FC = () => {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <AppLayout />;
};

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <MonitoringProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/" element={<ProtectedLayout />}>
              <Route index element={<Navigate to="/control-room" replace />} />
              <Route path="control-room" element={<ControlRoom />} />
              <Route path="joint-passport" element={<JointPassport />} />
              <Route path="sensor-analytics" element={<SensorAnalytics />} />
              <Route path="ai-diagnosis" element={<AIDiagnosis />} />
              <Route path="evidence" element={<Navigate to="/control-room" replace />} />
              <Route path="alerts" element={<Alerts />} />
              <Route path="settings" element={<SettingsPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/control-room" replace />} />
          </Routes>
        </MonitoringProvider>
      </AuthProvider>
    </BrowserRouter>
  );
};

export default App;
