import { Alert, Button, Center, Code, Group, Loader, Paper, PasswordInput, Stack, Text, Title } from '@mantine/core'
import { IconBooks } from '@tabler/icons-react'
import { useState, type FormEvent, type ReactNode } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router'
import { ApiError } from '../api/client'
import { useLogin, useSession, useSetup, useSetupStatus } from '../api/queries'

const RESET_CMD = 'powershell -NoProfile -ExecutionPolicy Bypass -File scripts/archeion.ps1 password set'

function message(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Wrong password.'
    if (error.status === 429) return 'Too many failed attempts. Wait a minute and try again.'
    return error.message
  }
  return "Can't reach the backend. Is it running?"
}

function Frame({ children }: { children: ReactNode }) {
  return (
    <Center h="100vh" p="md">
      <Paper withBorder shadow="sm" p="xl" radius="md" w={400}>
        <Stack>
          <Group gap="xs">
            <IconBooks size={26} />
            <Title order={3}>Archeion</Title>
          </Group>
          {children}
        </Stack>
      </Paper>
    </Center>
  )
}

/** A fresh start: no admin password yet, so create one (ADR 0011). */
function SetupForm({ minLength, onDone }: { minLength: number; onDone: () => void }) {
  const setup = useSetup()
  const [first, setFirst] = useState('')
  const [second, setSecond] = useState('')
  const short = first.length > 0 && first.length < minLength
  const mismatch = second.length > 0 && first !== second
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (short || mismatch || !first) return
    setup.mutate(first, { onSuccess: onDone })
  }
  return (
    <form onSubmit={submit}>
      <Stack>
        <Title order={4}>You&apos;re new here!</Title>
        <Text size="sm">
          Give Archeion a password to use. You&apos;ll log in with it from now on. Only a salted hash of it is stored,
          in the backend&apos;s database.
        </Text>
        <PasswordInput
          label="New admin password"
          description={`At least ${minLength} characters`}
          value={first}
          error={short ? `Use at least ${minLength} characters` : null}
          onChange={(e) => setFirst(e.currentTarget.value)}
          autoFocus
          autoComplete="new-password"
        />
        <PasswordInput
          label="Repeat it"
          value={second}
          error={mismatch ? "The two entries don't match" : null}
          onChange={(e) => setSecond(e.currentTarget.value)}
          autoComplete="new-password"
        />
        {setup.isError && <Alert color="red">{message(setup.error)}</Alert>}
        <Button type="submit" loading={setup.isPending} disabled={!first || short || first !== second}>
          Save password and log in
        </Button>
      </Stack>
    </form>
  )
}

export function LoginPage() {
  const session = useSession()
  const status = useSetupStatus()
  const login = useLogin()
  const navigate = useNavigate()
  const location = useLocation()
  const [secret, setSecret] = useState('')
  const from = (location.state as { from?: string } | null)?.from ?? '/'

  if (session.data) return <Navigate to={from} replace />
  if (status.isPending) {
    return (
      <Center h="100vh">
        <Loader />
      </Center>
    )
  }
  // Without the backend we can't tell a fresh start from a normal login, so say so.
  if (status.isError) {
    return (
      <Frame>
        <Alert color="red" title="Can't reach the backend">
          The viewer is up, but the backend isn&apos;t answering. Is its window still open? Start Archeion with
          start.bat (stop.bat first if half of it is running).
        </Alert>
        <Button onClick={() => status.refetch()} loading={status.isFetching}>
          Try again
        </Button>
      </Frame>
    )
  }

  if (status.data?.needed) {
    return (
      <Frame>
        {status.data.allowed ? (
          <SetupForm minLength={status.data.min_length} onDone={() => navigate(from, { replace: true })} />
        ) : (
          <Alert color="orange" title="No admin password yet">
            Archeion listens beyond this machine (<Code>ARCHEION_HOST</Code>), so the password can&apos;t be created
            here. Run this from the repo root, then reload: <Code block>{RESET_CMD}</Code>
          </Alert>
        )}
      </Frame>
    )
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!secret) return
    login.mutate(secret, {
      onSuccess: () => navigate(from, { replace: true }),
      onError: () => setSecret(''),
    })
  }

  return (
    <Frame>
      <form onSubmit={submit}>
        <Stack>
          <Text size="sm" c="dimmed">
            Log in with the admin password.
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
          <Text size="xs" c="dimmed">
            Forgot it? Set a new one from the repo root (it logs out every session): <Code>{RESET_CMD}</Code>
          </Text>
        </Stack>
      </form>
    </Frame>
  )
}
