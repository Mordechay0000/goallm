/**
 * Main App component with routing and RTL support
 */
import React, { useEffect } from 'react';
import './App.css';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import { CssBaseline } from '@mui/material';
import rtlPlugin from 'stylis-plugin-rtl';
import { CacheProvider } from '@emotion/react';
import createCache from '@emotion/cache';
import { theme } from './theme';
import { useAuthStore } from './store/authStore';
import LoginPage from './pages/LoginPage';
import RegisterWizard from './pages/RegisterWizard';
import HomePage from './pages/HomePage';
import FilterManagementPage from './pages/FilterManagementPage';
import ProfilesPage from './pages/ProfilesPage';
import RulesPage from './pages/RulesPage';
import SchedulesPage from './pages/SchedulesPage';
import ProfileEditPage from './pages/ProfileEditPage';
import AdminLayout from './components/AdminLayout';

// Create RTL cache
const cacheRtl = createCache({
  key: 'muirtl',
  stylisPlugins: [rtlPlugin],
});

// Protected Route component
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useAuthStore();
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" />;
};

function App() {
  const { init, isAuthenticated } = useAuthStore();

  useEffect(() => {
    init();
  }, [init]);

  return (
    <CacheProvider value={cacheRtl}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <BrowserRouter>
        <Routes>
          <Route path="/login" element={isAuthenticated ? <Navigate to="/" /> : <LoginPage />} />
          <Route path="/register" element={isAuthenticated ? <Navigate to="/" /> : <RegisterWizard />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <HomePage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/profile/edit"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <ProfileEditPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/filters"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <FilterManagementPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/profiles"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <ProfilesPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/profiles/:profileId/rules"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <RulesPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/profiles/:profileId/schedules"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <Navigate to="/schedules" replace />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/schedules"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <SchedulesPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
        </Routes>
      </BrowserRouter>
      </ThemeProvider>
    </CacheProvider>
  );
}

export default App;
