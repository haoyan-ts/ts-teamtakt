import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ProtectedRoute } from './routes/ProtectedRoute';
import { AppShell } from './components/layout/AppShell';
import { LoginPage } from './pages/LoginPage';
import { OnboardingPage } from './pages/OnboardingPage';
import { DashboardPage } from './pages/DashboardPage';
import { DailyFormPage } from './pages/DailyFormPage';
import { TeamPage } from './pages/TeamPage';
import { TeamRequestsPage } from './pages/TeamRequestsPage';
import { TeamBalanceSettingsPage } from './pages/TeamBalanceSettingsPage';
import { TeamThresholdSettingsPage } from './pages/TeamThresholdSettingsPage';
import { AdminListsPage } from './pages/AdminListsPage';
import { WeeklyReportPage } from './pages/WeeklyReportPage';
import { MonthlyReportPage } from './pages/MonthlyReportPage';
import { ExportPage } from './pages/ExportPage';
import { UnlockPage } from './pages/UnlockPage';
import { NotificationPreferencesPage } from './pages/NotificationPreferencesPage';
import { NotFoundPage } from './pages/NotFoundPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/onboarding" element={<ProtectedRoute allowLobby><OnboardingPage /></ProtectedRoute>} />
        <Route path="/" element={<ProtectedRoute><AppShell /></ProtectedRoute>}>
          <Route index element={<DashboardPage />} />
          <Route path="daily/:date?" element={<DailyFormPage />} />
          <Route path="team" element={<ProtectedRoute requireLeader><TeamPage /></ProtectedRoute>} />
          <Route path="team/requests" element={<ProtectedRoute requireLeader><TeamRequestsPage /></ProtectedRoute>} />
          <Route path="team/settings/balance" element={<ProtectedRoute requireLeader><TeamBalanceSettingsPage /></ProtectedRoute>} />
          <Route path="team/settings/thresholds" element={<ProtectedRoute requireLeader><TeamThresholdSettingsPage /></ProtectedRoute>} />
          <Route path="team/unlock" element={<ProtectedRoute requireLeader><UnlockPage /></ProtectedRoute>} />
          <Route path="reports/weekly/:week_start?" element={<WeeklyReportPage />} />
          <Route path="reports/monthly/:ym?" element={<MonthlyReportPage />} />
          <Route path="export" element={<ExportPage />} />
          <Route path="settings/notifications" element={<NotificationPreferencesPage />} />
          <Route path="admin/lists" element={<ProtectedRoute requireAdmin><AdminListsPage /></ProtectedRoute>} />
          <Route path="settings" element={<NotificationPreferencesPage />} />
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
          <Route path="settings" element={<NotificationPreferencesPage />} />
