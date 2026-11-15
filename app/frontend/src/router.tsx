import { Navigate, createBrowserRouter } from 'react-router'
import { LoginPage } from './auth/LoginPage'
import { RequireAuth } from './auth/RequireAuth'
import { DocPage } from './docs/DocPage'
import { FeedbackPage } from './feedback/FeedbackPage'
import { ThreadPage } from './feedback/ThreadPage'
import { Shell } from './layout/Shell'
import { GroupPage } from './projects/GroupPage'
import { ProjectPage } from './projects/ProjectPage'
import { ProjectsPage } from './projects/ProjectsPage'
import { DiagramsPage } from './pages/DiagramsPage'
import { RoadmapPage } from './pages/RoadmapPage'
import { SearchRoute } from './pages/SearchPage'

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <Shell />,
        children: [
          { index: true, element: <Navigate to="/docs/README.md" replace /> },
          { path: 'docs/*', element: <DocPage /> },
          { path: 'p/:source/*', element: <DocPage /> },
          { path: 'projects', element: <ProjectsPage /> },
          { path: 'projects/:id', element: <ProjectPage /> },
          { path: 'groups/:id', element: <GroupPage /> },
          { path: 'roadmap', element: <RoadmapPage /> },
          { path: 'diagrams', element: <DiagramsPage /> },
          { path: 'search', element: <SearchRoute /> },
          { path: 'feedback', element: <FeedbackPage /> },
          { path: 'feedback/:id', element: <ThreadPage /> },
        ],
      },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
])
