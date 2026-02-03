/**
 * Main App component with routing and RTL support
 */
import React, { useEffect } from 'react';
import './App.css';
import { BrowserRouter, Routes, Route, Navigate, useLocation, useSearchParams } from 'react-router-dom';
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
import AdminUsersPage from './pages/AdminUsersPage';
import AdminRequestsPage from './pages/AdminRequestsPage';
import AdminGlobalRulesPage from './pages/AdminGlobalRulesPage';
import AdminFilterSwitchesPage from './pages/AdminFilterSwitchesPage';
import MyRequestsPage from './pages/MyRequestsPage';
import AdminLayout from './components/AdminLayout';

// Create RTL cache
const cacheRtl = createCache({
  key: 'muirtl',
  stylisPlugins: [rtlPlugin],
});

// When authenticated user visits /login with redirect param, go to redirect destination
const LoginRedirect: React.FC = () => {
  const [searchParams] = useSearchParams();
  const redirect = searchParams.get('redirect');
  const to = redirect && redirect.startsWith('/') ? redirect : '/';
  return <Navigate to={to} replace />;
};

// Redirect /request-open and /request-change to /requests with params
const RequestRedirect: React.FC<{ to: string; requestType: 'open' | 'change' }> = ({ to, requestType }) => {
  const [searchParams] = useSearchParams();
  const url = searchParams.get('url') || '';
  const params = new URLSearchParams();
  if (url) params.set('url', url);
  params.set('request_type', requestType);
  return <Navigate to={`${to}?${params.toString()}`} replace />;
};

// Protected Route component - redirect to login with return URL
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useAuthStore();
  const location = useLocation();
  if (!isAuthenticated) {
    const redirect = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?redirect=${redirect}`} replace />;
  }
  return <>{children}</>;
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
          <Route path="/login" element={isAuthenticated ? <LoginRedirect /> : <LoginPage />} />
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
          <Route
            path="/admin/users"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <AdminUsersPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/requests"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <AdminRequestsPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/global-rules"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <AdminGlobalRulesPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/filter-switches"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <AdminFilterSwitchesPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/request-open"
            element={<RequestRedirect to="/requests" requestType="open" />}
          />
          <Route
            path="/request-change"
            element={<RequestRedirect to="/requests" requestType="change" />}
          />
          <Route
            path="/requests"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <MyRequestsPage />
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
