import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Item, ChatMessage, SearchSession } from '../types';

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
  mergeItems: (items: Item[]) => void;
  addItem: (item: Item) => void;
  updateItem: (id: string, update: Partial<Item>) => void;
  deleteItem: (id: string) => void;

  // In-flight uploads tracking
  inFlightMemoryIds: Set<string>;
  addInFlightMemory: (id: string) => void;
  removeInFlightMemory: (id: string) => void;

  // Search/Chat
  currentSession: SearchSession | null;
  setCurrentSession: (session: SearchSession | null) => void;
  addMessage: (message: ChatMessage) => void;
  addUserQuery: (query: string) => void;

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
            ],
            createdAt: new Date(),
          },
        });
        get().addRecentSearch(trimmed);
      },

      // Items
      items: [],
      setItems: (items) => set({ items }),
      mergeItems: (serverItems) =>
        set((state) => {
          // Merge server items with local items, preserving in-flight uploads
          const inFlightIds = state.inFlightMemoryIds;
          const localItems = state.items.filter((item) => inFlightIds.has(item.id));
          const serverItemsMap = new Map(serverItems.map((item) => [item.id, item]));
          const merged = [...serverItems];
          // Add any in-flight items not already in server response
          for (const item of localItems) {
            if (!serverItemsMap.has(item.id)) {
              merged.unshift(item);
            }
          }
          return { items: merged };
        }),
      addItem: (item) => set((state) => ({ items: [item, ...state.items] })),
      updateItem: (id, update) =>
        set((state) => ({
          items: state.items.map((item) => (item.id === id ? { ...item, ...update } : item)),
        })),
      deleteItem: (id) => set((state) => ({ items: state.items.filter((i) => i.id !== id) })),

      // In-flight uploads tracking
      inFlightMemoryIds: new Set(),
      addInFlightMemory: (id) =>
        set((state) => ({
          inFlightMemoryIds: new Set(state.inFlightMemoryIds).add(id),
        })),
      removeInFlightMemory: (id) =>
        set((state) => {
          const next = new Set(state.inFlightMemoryIds);
          next.delete(id);
          return { inFlightMemoryIds: next };
        }),

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
        // Don't persist inFlightMemoryIds - they're session-specific
      }),
    }
  )
);