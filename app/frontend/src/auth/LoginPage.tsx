import { Alert, Button, Center, Group, Paper, PasswordInput, Stack, Text, Title } from '@mantine/core'
import { IconBooks } from '@tabler/icons-react'
import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router'
import { ApiError } from '../api/client'
import { useLogin, useSession } from '../api/queries'

function message(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Wrong password.'
    if (error.status === 429) return 'Too many failed attempts. Wait a minute and try again.'
    return error.message
  }
  return "Can't reach the backend. Is it running?"
}

export function LoginPage() {
  const session = useSession()
  const login = useLogin()
  const navigate = useNavigate()
  const location = useLocation()
  const [secret, setSecret] = useState('')
  const from = (location.state as { from?: string } | null)?.from ?? '/'

  if (session.data) return <Navigate to={from} replace />

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!secret) return
    login.mutate(secret, {
      onSuccess: () => navigate(from, { replace: true }),
      onError: () => setSecret(''),
    })
  }

  return (
    <Center h="100vh" p="md">
      <Paper withBorder shadow="sm" p="xl" radius="md" w={380}>
        <form onSubmit={submit}>
          <Stack>
            <Group gap="xs">
              <IconBooks size={26} />
              <Title order={3}>Archeion</Title>
            </Group>
            <Text size="sm" c="dimmed">
              Log in with the admin password. Set or change it with set_admin_password.bat.
            </Text>
            <PasswordInput
              label="Admin password"
              value={secret}
              onChange={(e) => setSecret(e.currentTarget.value)}
              autoFocus
              autoComplete="current-password"
            />
            {login.isError && <Alert color="red">{message(login.error)}</Alert>}
            <Button type="submit" loading={login.isPending} disabled={!secret}>
              Log in
            </Button>
          </Stack>
        </form>
      </Paper>
    </Center>
  )
}
