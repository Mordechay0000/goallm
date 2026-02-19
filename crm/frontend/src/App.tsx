/**
 * Main App component with routing and RTL support.
 * מיתוג: theme + index.css (מערכת עיצוב) — DESIGN_SYSTEM.md
 */
import React, { useEffect } from 'react';
import './index.css';
import './App.css';
import { BrowserRouter, Routes, Route, Navigate, useLocation, useSearchParams } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import { CssBaseline } from '@mui/material';
import rtlPlugin from 'stylis-plugin-rtl';
import { CacheProvider } from '@emotion/react';
import createCache from '@emotion/cache';
import { theme } from './theme';
import { useAuthStore } from './store/authStore';
import { authApi } from './api/auth';
import LoginPage from './pages/LoginPage';
import RegisterWizard from './pages/RegisterWizard';
import SetupPage from './pages/SetupPage';
import BindPage from './pages/BindPage';
import ConnectionsPage from './pages/ConnectionsPage';
import HomePage from './pages/HomePage';
import FilterManagementPage from './pages/FilterManagementPage';
import ProfilesPage from './pages/ProfilesPage';
import RulesPage from './pages/RulesPage';
import SchedulesPage from './pages/SchedulesPage';
import ProfileEditPage from './pages/ProfileEditPage';
import AdminUsersPage from './pages/AdminUsersPage';
import AdminRequestsPage from './pages/AdminRequestsPage';
import AdminGlobalRulesPage from './pages/AdminGlobalRulesPage';
import AdminAllowedFilesPage from './pages/AdminAllowedFilesPage';
import AdminFilterSwitchesPage from './pages/AdminFilterSwitchesPage';
import MyRequestsPage from './pages/MyRequestsPage';
import RequestFilePage from './pages/RequestFilePage';
import MySupportPage from './pages/MySupportPage';
import AdminSupportPage from './pages/AdminSupportPage';
import SupportConversationPage from './pages/SupportConversationPage';
import SupportNewTicketPage from './pages/SupportNewTicketPage';
import ToolsPage from './pages/ToolsPage';
import TrafficRecordingPage from './pages/TrafficRecordingPage';
import TrafficViewPage from './pages/TrafficViewPage';
import SurfAdminCheckPage from './pages/SurfAdminCheckPage';
import SurfBlockPage from './pages/SurfBlockPage';
import SurfUpdateRulePage from './pages/SurfUpdateRulePage';
import AdminLayout from './components/AdminLayout';
import { DOCUMENT_TITLE } from './brand';

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

// Login route: when no users exist, redirect to setup; else show login (or redirect if already authenticated)
const LoginRoute: React.FC = () => {
  const [searchParams] = useSearchParams();
  const { isAuthenticated } = useAuthStore();
  const [setupChecked, setSetupChecked] = React.useState(false);
  const [needsSetup, setNeedsSetup] = React.useState(false);
  const redirect = searchParams.get('redirect') || '';
  const isBindFlowReLogin = redirect.includes('/bind') && (redirect.includes('from_login=1') || redirect.includes('from_login%3D1'));

  React.useEffect(() => {
    if (isAuthenticated) {
      setSetupChecked(true);
      setNeedsSetup(false);
      return;
    }
    let cancelled = false;
    authApi.getSetupStatus().then((res) => {
      if (!cancelled) {
        setNeedsSetup(res.needs_setup);
        setSetupChecked(true);
      }
    }).catch(() => {
      if (!cancelled) setSetupChecked(true);
    });
    return () => { cancelled = true; };
  }, [isAuthenticated]);

  if (isAuthenticated && !isBindFlowReLogin) return <LoginRedirect />;
  if (!setupChecked) return null; // or a tiny spinner
  if (needsSetup) return <Navigate to="/setup" replace />;
  return <LoginPage />;
};

// True when redirect URL is the bind flow (so we allow register/login even when already logged in)
function isBindFlowRedirect(redirect: string): boolean {
  return redirect.includes('/bind') && (redirect.includes('from_login=1') || redirect.includes('from_login%3D1'));
}

// Register route: when needs_setup, redirect to /setup (first user = admin); when coming from bind flow show wizard; else redirect if authenticated
const RegisterRoute: React.FC = () => {
  const [searchParams] = useSearchParams();
  const { isAuthenticated } = useAuthStore();
  const [setupChecked, setSetupChecked] = React.useState(false);
  const [needsSetup, setNeedsSetup] = React.useState(false);
  const redirect = searchParams.get('redirect') || '';

  React.useEffect(() => {
    if (isAuthenticated && !isBindFlowRedirect(redirect)) return;
    let cancelled = false;
    authApi.getSetupStatus().then((res) => {
      if (!cancelled) {
        setNeedsSetup(res.needs_setup);
        setSetupChecked(true);
      }
    }).catch(() => {
      if (!cancelled) setSetupChecked(true);
    });
    return () => { cancelled = true; };
  }, [isAuthenticated, redirect]);

  if (isAuthenticated && !isBindFlowRedirect(redirect)) return <Navigate to="/" replace />;
  if (!setupChecked) return null;
  if (needsSetup) return <Navigate to="/setup" replace />;
  return <RegisterWizard />;
};

// Redirect /request-open and /request-change to מערכת הפניות (support/new) with attach type and url
const RequestRedirect: React.FC<{ requestType: 'open' | 'change' }> = ({ requestType }) => {
  const [searchParams] = useSearchParams();
  const url = searchParams.get('url') || '';
  const params = new URLSearchParams();
  params.set('attach', requestType);
  if (url) params.set('url', url);
  return <Navigate to={`/support/new?${params.toString()}`} replace />;
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
  const { init } = useAuthStore();

  useEffect(() => {
    init();
  }, [init]);

  useEffect(() => {
    document.title = DOCUMENT_TITLE;
  }, []);

  return (
    <CacheProvider value={cacheRtl}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <BrowserRouter>
        <Routes>
          <Route path="/surf-admin-check" element={<SurfAdminCheckPage />} />
          <Route path="/setup" element={<SetupPage />} />
          <Route path="/login" element={<LoginRoute />} />
          <Route path="/register" element={<RegisterRoute />} />
          <Route path="/bind" element={<BindPage />} />
          <Route
            path="/connections"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <ConnectionsPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
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
            path="/admin/global-files"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <AdminAllowedFilesPage />
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
            path="/admin/surf-block"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <SurfBlockPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/surf-update-rule"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <SurfUpdateRulePage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/request-open"
            element={<RequestRedirect requestType="open" />}
          />
          <Route
            path="/request-change"
            element={<RequestRedirect requestType="change" />}
          />
          <Route
            path="/request-file"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <RequestFilePage />
                </AdminLayout>
              </ProtectedRoute>
            }
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
          <Route
            path="/support"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <MySupportPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/support/new"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <SupportNewTicketPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/support/:ticketId"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <SupportConversationPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/support"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <AdminSupportPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/support/:ticketId"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <SupportConversationPage isAdmin />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/tools"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <ToolsPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/tools/traffic"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <TrafficRecordingPage />
                </AdminLayout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/tools/traffic/view/:token"
            element={
              <ProtectedRoute>
                <AdminLayout>
                  <TrafficViewPage />
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
