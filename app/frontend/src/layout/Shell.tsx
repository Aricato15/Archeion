import {
  ActionIcon,
  AppShell,
  Badge,
  Burger,
  Divider,
  Group,
  Kbd,
  Loader,
  NavLink,
  ScrollArea,
  Text,
  TextInput,
  Tooltip,
  useComputedColorScheme,
  useMantineColorScheme,
} from '@mantine/core'
import { useDisclosure, useHotkeys } from '@mantine/hooks'
import {
  IconBooks,
  IconChartDots3,
  IconLogout,
  IconMessages,
  IconMoon,
  IconRoad,
  IconSearch,
  IconSun,
} from '@tabler/icons-react'
import { useRef, useState } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router'
import { useLogout, useTree, useVersion } from '../api/queries'
import { useEvents } from '../events/useEvents'
import { DocTree } from './DocTree'
import { FeedbackBadge } from './FeedbackBadge'

const NAV = [
  { to: '/roadmap', label: 'Roadmap', icon: IconRoad },
  { to: '/diagrams', label: 'Diagrams', icon: IconChartDots3 },
  { to: '/feedback', label: 'Feedback', icon: IconMessages },
]

export function Shell() {
  const [opened, { toggle, close }] = useDisclosure()
  const location = useLocation()
  const navigate = useNavigate()
  const logout = useLogout()
  const tree = useTree()
  const version = useVersion()
  const { setColorScheme } = useMantineColorScheme()
  const scheme = useComputedColorScheme('light')
  const [q, setQ] = useState('')
  const searchRef = useRef<HTMLInputElement>(null)
  useEvents()
  useHotkeys([['/', () => searchRef.current?.focus()]])

  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{ width: 280, breakpoint: 'sm', collapsed: { mobile: !opened } }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group gap="xs" wrap="nowrap">
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
            <IconBooks size={22} />
            <Text fw={700} component={Link} to="/" c="inherit" td="none">
              Archeion
            </Text>
            <Tooltip label={`Frontend ${__APP_VERSION__} · backend ${version.data?.version ?? '…'}`}>
              <Badge variant="light" size="sm">
                v{version.data?.version ?? __APP_VERSION__}
              </Badge>
            </Tooltip>
          </Group>
          <Group gap="xs" wrap="nowrap">
            <TextInput
              ref={searchRef}
              size="xs"
              w={{ base: 140, sm: 260 }}
              placeholder="Search docs"
              leftSection={<IconSearch size={14} />}
              rightSection={<Kbd size="xs">/</Kbd>}
              value={q}
              onChange={(e) => setQ(e.currentTarget.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && q.trim().length >= 2) {
                  navigate(`/search?q=${encodeURIComponent(q.trim())}`, { state: { nonce: Date.now() } })
                  setQ('')
                  searchRef.current?.blur()
                }
                if (e.key === 'Escape') searchRef.current?.blur()
              }}
            />
            <FeedbackBadge />
            <Tooltip label="Toggle color scheme">
              <ActionIcon
                variant="default"
                size="lg"
                aria-label="Toggle color scheme"
                onClick={() => setColorScheme(scheme === 'dark' ? 'light' : 'dark')}
              >
                {scheme === 'dark' ? <IconSun size={18} /> : <IconMoon size={18} />}
              </ActionIcon>
            </Tooltip>
            <Tooltip label="Log out">
              <ActionIcon
                variant="default"
                size="lg"
                aria-label="Log out"
                loading={logout.isPending}
                onClick={() => logout.mutate(undefined, { onSettled: () => navigate('/login') })}
              >
                <IconLogout size={18} />
              </ActionIcon>
            </Tooltip>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="xs">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            component={Link}
            to={item.to}
            label={item.label}
            leftSection={<item.icon size={18} />}
            active={location.pathname.startsWith(item.to)}
            onClick={close}
          />
        ))}
        <Divider my="xs" label="docs/" labelPosition="left" />
        <AppShell.Section grow component={ScrollArea}>
          {tree.isPending && <Loader size="sm" m="sm" />}
          {tree.data && <DocTree tree={tree.data} onNavigate={close} />}
        </AppShell.Section>
      </AppShell.Navbar>

      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  )
}
