import {
  ActionIcon,
  AppShell,
  Box,
  Badge,
  Burger,
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
import { useDisclosure, useHotkeys, useLocalStorage } from '@mantine/hooks'
import {
  IconBooks,
  IconBox,
  IconHome,
  IconChartDots3,
  IconLogout,
  IconMessages,
  IconMoon,
  IconRoad,
  IconRoute,
  IconSearch,
  IconDownload,
  IconSettings,
  IconSun,
  IconTerminal2,
} from '@tabler/icons-react'
import { useMemo, useRef, useState } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router'
import { useLogout, useRegistry, useTree, useVersion } from '../api/queries'
import { REGISTRY, SELF } from '../api/types'
import { InboxTerminalBadge } from '../runner/InboxTerminal'
import { OnDemandBadge } from '../runner/OnDemand'
import { DEFAULT_LINKS, LinkContextValue, type LinkContext } from '../docs/links'
import { useEvents } from '../events/useEvents'
import { DocTree } from './DocTree'
import { FeedbackBadge } from './FeedbackBadge'
import { GuidePanel } from './GuidePanel'
import { ProjectTree } from './ProjectTree'

const NAV = [
  { to: '/', label: 'Home', icon: IconHome },
  { to: '/roadmap', label: 'Roadmap', icon: IconRoad },
  { to: '/diagrams', label: 'Diagrams', icon: IconChartDots3 },
  { to: '/feedback', label: 'Feedback', icon: IconMessages },
  // an ordinary doc, so it gets diagrams, history and comments like any other
  { to: '/docs/guides/use-cases.md', label: 'Use cases', icon: IconRoute },
  { to: '/updates', label: 'Updates', icon: IconDownload },
  { to: '/settings', label: 'Settings', icon: IconSettings },
]

// The projects overview heads the project tree at the top of the sidebar; the other pages follow it.
const PROJECTS_NAV = { to: '/projects', label: 'Projects', icon: IconBox }

function NavItem({ item, pathname, onClick }: { item: (typeof NAV)[number]; pathname: string; onClick: () => void }) {
  return (
    <NavLink
      component={Link}
      to={item.to}
      label={item.label}
      leftSection={<item.icon size={18} />}
      active={pathname.startsWith(item.to) || (item.to === '/projects' && pathname.startsWith('/groups'))}
      onClick={onClick}
    />
  )
}

/** One tinted block of the sidebar, so the sections read apart at a glance (the tint adapts to light and dark). */
function SideSection({ color, label, children }: { color: string; label?: string; children: React.ReactNode }) {
  return (
    <Box
      p={4}
      mb="xs"
      style={{ borderRadius: 'var(--mantine-radius-md)', background: `var(--mantine-color-${color}-light)` }}
    >
      {label && (
        <Text size="xs" fw={600} c={`${color}.7`} px="sm" py={4} tt="uppercase">
          {label}
        </Text>
      )}
      {children}
    </Box>
  )
}

export function Shell() {
  const [opened, { toggle, close }] = useDisclosure()
  const location = useLocation()
  const navigate = useNavigate()
  const logout = useLogout()
  const tree = useTree(SELF)
  const registryTree = useTree(REGISTRY)
  const registry = useRegistry()
  // Where every source lives, so links between docs of different projects resolve (links.ts).
  const links = useMemo<LinkContext>(() => {
    const bases = { ...DEFAULT_LINKS.bases }
    for (const p of registry.data?.projects ?? []) if (p.path && p.available) bases[p.id] = p.path
    return { bases }
  }, [registry.data])
  const version = useVersion()
  const { setColorScheme } = useMantineColorScheme()
  const scheme = useComputedColorScheme('light')
  const [q, setQ] = useState('')
  const searchRef = useRef<HTMLInputElement>(null)
  // The Claude CLI panel on the right; whether it's open is remembered in this browser.
  const [guide, setGuide] = useLocalStorage({ key: 'archeion.guide-panel', defaultValue: false })
  const toggleGuide = () => setGuide((v) => !v)
  useEvents()
  useHotkeys([
    ['/', () => searchRef.current?.focus()],
    ['mod+i', toggleGuide],
  ])

  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{ width: 280, breakpoint: 'sm', collapsed: { mobile: !opened } }}
      aside={{ width: { md: 340, lg: 400 }, breakpoint: 'md', collapsed: { desktop: !guide, mobile: !guide } }}
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
            <InboxTerminalBadge />
            <OnDemandBadge />
            <FeedbackBadge />
            <Tooltip label={guide ? 'Hide the Claude CLI guide (Ctrl+I)' : 'Show the Claude CLI guide (Ctrl+I)'}>
              <ActionIcon
                variant={guide ? 'filled' : 'default'}
                size="lg"
                aria-label="Claude CLI guide"
                aria-pressed={guide}
                onClick={toggleGuide}
              >
                <IconTerminal2 size={18} />
              </ActionIcon>
            </Tooltip>
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
        <AppShell.Section grow component={ScrollArea} viewportProps={{ style: { overscrollBehavior: 'contain' } }}>
          <SideSection color="blue">
            <NavItem item={PROJECTS_NAV} pathname={location.pathname} onClick={close} />
            {registry.data && registry.data.projects.length > 0 && (
              <ProjectTree registry={registry.data} onNavigate={close} />
            )}
          </SideSection>
          <SideSection color="gray">
            {NAV.map((item) => (
              <NavItem key={item.to} item={item} pathname={location.pathname} onClick={close} />
            ))}
          </SideSection>
          <SideSection color="violet" label="registry/ (private)">
            {registryTree.data && registryTree.data.children?.length ? (
              <DocTree tree={registryTree.data} source={REGISTRY} onNavigate={close} />
            ) : (
              <Text size="xs" c="dimmed" px="sm">
                No registry yet. Run setup.bat to create it from registry.example/.
              </Text>
            )}
          </SideSection>
          <SideSection color="teal" label="archeion docs/">
            {tree.isPending && <Loader size="sm" m="sm" />}
            {tree.data && <DocTree tree={tree.data} onNavigate={close} />}
          </SideSection>
        </AppShell.Section>
      </AppShell.Navbar>

      <LinkContextValue.Provider value={links}>
        <GuidePanel opened={guide} onClose={() => setGuide(false)} />
        <AppShell.Main>
          <Outlet />
        </AppShell.Main>
      </LinkContextValue.Provider>
    </AppShell>
  )
}
