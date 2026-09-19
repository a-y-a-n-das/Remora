import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';

import { Sidebar } from './components/Sidebar';
import { Home } from './pages/Home';
import { SearchSession } from './pages/SearchSession';
import { AllItems } from './pages/AllItems';
import { useAppStore } from './store';

function AppLayout() {
  const {
    activeView,
    currentSession,
    sidebarCollapsed,
  } = useAppStore();

  return (
    <div className="min-h-screen bg-bg flex">
      <Sidebar />

      <div className={`flex-1 flex flex-col min-w-0 transition-[margin] duration-300 ${sidebarCollapsed ? 'ml-16' : 'ml-64'}`}>
        <AnimatePresence mode="wait">
          {activeView === 'home' && (
            <motion.div
              key="home"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex-1"
            >
              <Home />
            </motion.div>
          )}

          {activeView === 'allItems' && (
            <motion.div
              key="allItems"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex-1"
            >
              <AllItems />
            </motion.div>
          )}

          {activeView === 'search' && (
            <motion.div
              key="search"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex-1"
            >
              {currentSession ? (
                <SearchSession query={currentSession.query} />
              ) : (
                <Home />
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AppLayout />} />

        <Route
          path="*"
          element={<Navigate to="/" replace />}
        />
      </Routes>
    </BrowserRouter>
  );
}