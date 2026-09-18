import { RemoraIcon } from './Logo';
import {
  Home,
  Grid,
  ChevronLeft,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '../store';
import { recentSearches as defaultRecentSearches } from '../data/mockData';

export function Sidebar() {
  const {
    activeView,
    setActiveView,
    recentSearches,
    startSearch,
    sidebarCollapsed,
    toggleSidebar,
  } = useAppStore();

  const homeActive =
    activeView === 'home' || activeView === 'search';

  const allActive = activeView === 'allItems';
  const visibleRecentSearches = Array.from(
    new Set([...defaultRecentSearches, ...recentSearches])
  ).slice(0, 8);

  return (
    <aside
      className={`
        fixed left-0 top-0 z-40 h-full flex flex-col
        bg-bg-sidebar border-r border-border/30
        transition-all duration-300 ease-in-out
        ${sidebarCollapsed ? 'w-16' : 'w-64'}
      `}
    >
      <div className="flex flex-col h-full">
        {/* Logo */}
        <div className="flex items-center gap-3 px-5 py-5">
          {sidebarCollapsed ? (
            <button
              type="button"
              onClick={toggleSidebar}
              className="mx-auto flex-shrink-0 -translate-x-3 rounded-lg p-1 transition-colors hover:bg-white/5"
              aria-label="Expand sidebar"
            >
              <RemoraIcon size={44} />
            </button>
          ) : (
            <RemoraIcon size={56} />
          )}

          <AnimatePresence mode="wait">
            {!sidebarCollapsed && (
              <motion.span
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                className="font-semibold text-lg text-text whitespace-nowrap"
              >
                Remora
              </motion.span>
            )}
          </AnimatePresence>
          {!sidebarCollapsed && (
            <button
              type="button"
              onClick={toggleSidebar}
              className="ml-auto rounded-lg p-1.5 text-muted hover:bg-white/5 hover:text-text transition-colors"
              aria-label="Collapse sidebar"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
          )}
        </div>

        <div className="mx-5 border-t border-border/30" />

        {/* Navigation */}
        <nav className="px-3 py-5">
          <NavItem
            icon={<Home size={18} />}
            label="Home"
            active={homeActive}
            onClick={() => setActiveView('home')}
            collapsed={sidebarCollapsed}
          />

          <NavItem
            icon={<Grid size={18} />}
            label="All items"
            active={allActive}
            onClick={() => setActiveView('allItems')}
            collapsed={sidebarCollapsed}
          />
        </nav>

        <div className="mx-5 border-t border-border/30" />

        {/* Recent searches */}
        <AnimatePresence mode="wait">
          {!sidebarCollapsed && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="px-3"
            >
              <div className="text-xs font-medium text-muted mb-2 px-2">
                Recent searches
              </div>

              {visibleRecentSearches.map((query) => (
                  <RecentItem
                    key={query}
                    label={query}
                    onClick={() => startSearch(query)}
                  />
              ))}
            </motion.div>
          )}
        </AnimatePresence>

      </div>
    </aside>
  );
}

interface NavItemProps {
  icon: React.ReactNode;
  label: string;
  active: boolean;
  onClick: () => void;
  collapsed: boolean;
}

function NavItem({
  icon,
  label,
  active,
  onClick,
  collapsed,
}: NavItemProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`
        w-full flex items-center gap-3 px-3 py-2.5 rounded-lg
        transition-all duration-150
        ${
          active
            ? 'bg-accent/15 text-text ring-1 ring-accent/35'
            : 'text-muted hover:text-text hover:bg-white/5'
        }
        ${collapsed ? 'justify-center px-2' : ''}
      `}
    >
      <span className="flex-shrink-0">
        {icon}
      </span>

      <AnimatePresence mode="wait">
        {!collapsed && (
          <motion.span
            initial={{ opacity: 0, width: 0 }}
            animate={{ opacity: 1, width: 'auto' }}
            exit={{ opacity: 0, width: 0 }}
            className="whitespace-nowrap font-medium text-sm"
          >
            {label}
          </motion.span>
        )}
      </AnimatePresence>
    </button>
  );
}

interface RecentItemProps {
  label: string;
  onClick: () => void;
}

function RecentItem({
  label,
  onClick,
}: RecentItemProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left text-sm text-muted hover:text-text hover:bg-white/5 transition-colors"
    >
      <svg
        className="w-4 h-4 flex-shrink-0"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
        />
      </svg>

      <span className="truncate">
        {label}
      </span>
    </button>
  );
}