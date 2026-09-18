import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Item, ChatMessage, SearchSession, UploadState } from '../types';
import { buildAssistantReply } from '../data/mockData';

interface AppState {
  // Sidebar
  activeView: 'home' | 'allItems' | 'search';
  setActiveView: (view: 'home' | 'allItems' | 'search') => void;

  // Recent searches
  recentSearches: string[];
  addRecentSearch: (query: string) => void;
  startSearch: (query: string) => void;

  // Items
  items: Item[];
  setItems: (items: Item[]) => void;
  addItem: (item: Item) => void;
  deleteItem: (id: string) => void;

  // Search/Chat
  currentSession: SearchSession | null;
  setCurrentSession: (session: SearchSession | null) => void;
  addMessage: (message: ChatMessage) => void;
  addUserQuery: (query: string) => void;

  // Upload
  uploadState: UploadState;
  setUploadState: (state: Partial<UploadState>) => void;
  resetUploadState: () => void;

  // Upload Modal
  uploadOpen: boolean;
  setUploadOpen: (open: boolean) => void;

  // UI
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      // Sidebar
      activeView: 'home',
      setActiveView: (view) => set({ activeView: view }),

      // Recent searches
      recentSearches: [],
      addRecentSearch: (query) =>
        set((state) => {
          const filtered = state.recentSearches.filter((s) => s !== query);
          return { recentSearches: [query, ...filtered].slice(0, 8) };
        }),
      startSearch: (query) => {
        const trimmed = query.trim();
        if (!trimmed) return;
        set({
          activeView: 'search',
          currentSession: {
            id: Date.now().toString(),
            query: trimmed,
            messages: [
              {
                id: `${Date.now()}-user`,
                role: 'user',
                content: trimmed,
                timestamp: new Date(),
              },
              buildAssistantReply(trimmed),
            ],
            createdAt: new Date(),
          },
        });
        get().addRecentSearch(trimmed);
      },

      // Items
      items: [],
      setItems: (items) => set({ items }),
      addItem: (item) => set((state) => ({ items: [item, ...state.items] })),
      deleteItem: (id) => set((state) => ({ items: state.items.filter((i) => i.id !== id) })),

      // Search/Chat
      currentSession: null,
      setCurrentSession: (session) => set({ currentSession: session }),
      addMessage: (message: ChatMessage) =>
        set((state) => {
          if (!state.currentSession) return state;
          return {
            currentSession: {
              ...state.currentSession,
              messages: [...state.currentSession.messages, { ...message, id: Date.now().toString(), timestamp: new Date() }],
            },
          };
        }),
      addUserQuery: (query: string) =>
        set((state) => {
          const newQuery = query.trim();
          if (!newQuery) return state;

          const userMsg = {
            id: Date.now().toString(),
            role: 'user' as const,
            content: newQuery,
            timestamp: new Date(),
          };

          const assistantMsg = {
            id: (Date.now() + 1).toString(),
            role: 'assistant' as const,
            content: `I found some matching items in your collection for "${newQuery}".`,
            results: [],
            timestamp: new Date(),
          };

          if (!state.currentSession) {
            return {
              currentSession: {
                id: Date.now().toString(),
                query: newQuery,
                messages: [
                  { ...userMsg, id: userMsg.id, timestamp: new Date() },
                  { ...assistantMsg, id: (Date.now() + 1).toString(), timestamp: new Date() },
                ],
                createdAt: new Date(),
              },
              recentSearches: [newQuery, ...get().recentSearches.filter((s) => s !== newQuery)].slice(0, 8),
            };
          }

          return {
            currentSession: {
              ...state.currentSession,
              messages: [
                ...state.currentSession.messages,
                { ...userMsg, id: userMsg.id, timestamp: new Date() },
                { ...assistantMsg, id: (Date.now() + 1).toString(), timestamp: new Date() },
              ],
            },
            recentSearches: [newQuery, ...get().recentSearches.filter((s) => s !== newQuery)].slice(0, 8),
          };
        }),

      // Upload
      uploadState: { status: 'idle', progress: 0, files: [] },
      setUploadState: (state) =>
        set((prev) => ({ uploadState: { ...prev.uploadState, ...state } })),
      resetUploadState: () => set({ uploadState: { status: 'idle', progress: 0, files: [] } }),

      // Upload Modal
      uploadOpen: false,
      setUploadOpen: (open) => set({ uploadOpen: open }),

      // UI
      sidebarCollapsed: false,
      toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
    }),
    {
      name: 'remora-store',
      partialize: (state) => ({
        recentSearches: state.recentSearches,
        items: state.items,
        sidebarCollapsed: state.sidebarCollapsed,
      }),
    }
  )
);