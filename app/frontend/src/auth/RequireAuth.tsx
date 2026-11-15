import { Alert, Button, Center, Loader, Stack } from '@mantine/core'
import { Navigate, Outlet, useLocation } from 'react-router'
import { useSession } from '../api/queries'

/** Nothing but the login page renders until the session check succeeds. */
export function RequireAuth() {
  const session = useSession()
  const location = useLocation()

  if (session.isPending) {
    return (
      <Center h="100vh">
        <Loader />
      </Center>
    )
  }
  if (session.isError) {
    return (
      <Center h="100vh">
        <Stack align="center">
          <Alert color="red" title="Can't reach the backend">
            {session.error.message}. Is it running? Start it with start.bat.
          </Alert>
          <Button onClick={() => session.refetch()}>Try again</Button>
        </Stack>
      </Center>
    )
  }
  if (!session.data) {
    const from = location.pathname + location.search + location.hash
    return <Navigate to="/login" replace state={{ from }} />
  }
  return <Outlet />
}
