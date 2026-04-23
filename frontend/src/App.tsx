import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext';
import { ProtectedRoute } from './routes/ProtectedRoute';
import { AppShell } from './components/layout/AppShell';
import { LoginPage } from './pages/LoginPage';
import { LocalLoginPage } from './pages/LocalLoginPage';
import { OnboardingPage } from './pages/OnboardingPage';
import { DashboardPage } from './pages/DashboardPage';
import { DailyFormPage } from './pages/DailyFormPage';
import { TeamPage } from './pages/TeamPage';
import { TeamRequestsPage } from './pages/TeamRequestsPage';
import { TeamBalanceSettingsPage } from './pages/TeamBalanceSettingsPage';
import { TeamThresholdSettingsPage } from './pages/TeamThresholdSettingsPage';
import { AdminListsPage } from './pages/AdminListsPage';
import { AdminTeamsPage } from './pages/AdminTeamsPage';
import { AdminTeamDetailPage } from './pages/AdminTeamDetailPage';
import { AdminDebugPage } from './pages/AdminDebugPage';
import { TeamMembersPage } from './pages/TeamMembersPage';
import { WeeklyReportPage } from './pages/WeeklyReportPage';
import { MonthlyReportPage } from './pages/MonthlyReportPage';
import { ExportPage } from './pages/ExportPage';
import { UnlockPage } from './pages/UnlockPage';
import { NotificationPreferencesPage } from './pages/NotificationPreferencesPage';
import { QuarterlyReportPage } from './pages/QuarterlyReportPage';
import { TeamQuarterlyReportPage } from './pages/TeamQuarterlyReportPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { CrossTeamSharingPage } from './pages/CrossTeamSharingPage';
import { ProjectsPage } from './pages/ProjectsPage';
import { ProjectDetailPage } from './pages/ProjectDetailPage';
import { ProfileSettingsPage } from './pages/ProfileSettingsPage';

function App() {
  return (
    <ThemeProvider>
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/admin-login" element={<LocalLoginPage />} />
        <Route path="/onboarding" element={<ProtectedRoute allowLobby><OnboardingPage /></ProtectedRoute>} />
        <Route path="/" element={<ProtectedRoute><AppShell /></ProtectedRoute>}>
          <Route index element={<DashboardPage />} />
          <Route path="daily/:date?" element={<DailyFormPage />} />
          <Route path="team/members" element={<TeamMembersPage />} />
          <Route path="team" element={<ProtectedRoute requireLeader><TeamPage /></ProtectedRoute>} />
          <Route path="team/requests" element={<ProtectedRoute requireLeader><TeamRequestsPage /></ProtectedRoute>} />
          <Route path="team/settings/balance" element={<ProtectedRoute requireLeader><TeamBalanceSettingsPage /></ProtectedRoute>} />
          <Route path="team/settings/thresholds" element={<ProtectedRoute requireLeader><TeamThresholdSettingsPage /></ProtectedRoute>} />
          <Route path="team/unlock" element={<ProtectedRoute requireLeader><UnlockPage /></ProtectedRoute>} />
          <Route path="team/sharing" element={<ProtectedRoute requireLeader><CrossTeamSharingPage /></ProtectedRoute>} />
          <Route path="projects" element={<ProjectsPage />} />
          <Route path="projects/:id" element={<ProjectDetailPage />} />
          <Route path="reports/weekly/:week_start?" element={<WeeklyReportPage />} />
          <Route path="reports/monthly/:ym?" element={<MonthlyReportPage />} />
          <Route path="reports/quarterly/:quarter?" element={<QuarterlyReportPage />} />
          <Route path="team/quarterly/:quarter?" element={<ProtectedRoute requireLeader><TeamQuarterlyReportPage /></ProtectedRoute>} />
          <Route path="export" element={<ExportPage />} />
          <Route path="settings/notifications" element={<NotificationPreferencesPage />} />
          <Route path="settings/profile" element={<ProfileSettingsPage />} />
          <Route path="admin/lists" element={<ProtectedRoute requireAdmin><AdminListsPage /></ProtectedRoute>} />
          <Route path="admin/teams" element={<ProtectedRoute requireAdmin><AdminTeamsPage /></ProtectedRoute>} />
          <Route path="admin/teams/:teamId" element={<ProtectedRoute requireAdmin><AdminTeamDetailPage /></ProtectedRoute>} />
          <Route path="admin/debug" element={<ProtectedRoute requireAdmin><AdminDebugPage /></ProtectedRoute>} />
          <Route path="settings" element={<NotificationPreferencesPage />} />
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
          <Route path="settings" element={<NotificationPreferencesPage />} />
