import { Navigate, createBrowserRouter } from 'react-router'
import { LoginPage } from './auth/LoginPage'
import { RequireAuth } from './auth/RequireAuth'
import { PrintReport } from './report/PrintReport'
import { DocPage } from './docs/DocPage'
import { FeedbackPage } from './feedback/FeedbackPage'
import { ThreadPage } from './feedback/ThreadPage'
import { Shell } from './layout/Shell'
import { GroupPage } from './projects/GroupPage'
import { ProjectPage } from './projects/ProjectPage'
import { ProjectsPage } from './projects/ProjectsPage'
import { DiagramsPage } from './pages/DiagramsPage'
import { HomePage } from './pages/HomePage'
import { RoadmapPage } from './pages/RoadmapPage'
import { SearchRoute } from './pages/SearchPage'
import { SettingsPage } from './pages/SettingsPage'
import { UpdatesPage } from './pages/UpdatesPage'

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    element: <RequireAuth />,
    children: [
      // The report's print page has no shell: it is what becomes the PDF (ADR 0025).
      { path: 'print/report/:project', element: <PrintReport /> },
      {
        element: <Shell />,
        children: [
          { index: true, element: <HomePage /> },
          { path: 'docs/*', element: <DocPage /> },
          { path: 'p/:source/*', element: <DocPage /> },
          { path: 'projects', element: <ProjectsPage /> },
          { path: 'projects/:id', element: <ProjectPage /> },
          { path: 'groups/:id', element: <GroupPage /> },
          { path: 'roadmap', element: <RoadmapPage /> },
          { path: 'diagrams', element: <DiagramsPage /> },
          { path: 'updates', element: <UpdatesPage /> },
          { path: 'updates/:version', element: <UpdatesPage /> },
          { path: 'search', element: <SearchRoute /> },
          { path: 'settings', element: <SettingsPage /> },
          { path: 'feedback', element: <FeedbackPage /> },
          { path: 'feedback/:id', element: <ThreadPage /> },
        ],
      },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
])
