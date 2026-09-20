import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type {
  Item,
  ChatMessage,
  ChatSession,
  SearchSession,
} from '../types';

interface AppState {
  // Sidebar
  activeView: 'home' | 'allItems' | 'search';
  setActiveView: (view: 'home' | 'allItems' | 'search') => void;

  // Recent searches
  recentSearches: string[];
  addRecentSearch: (query: string) => void;
  startSearch: (query: string) => string;

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

  // Chat sessions
  sessions: Record<string, ChatSession>;
  activeSessionId: string | null;
  createSession: (query: string) => string;
  createEmptySession: () => string;
  addMessageToSession: (
    sessionId: string,
    message: ChatMessage,
  ) => void;
  updateSessionTitle: (
    sessionId: string,
    title: string,
  ) => void;
  deleteSession: (sessionId: string) => void;
  setActiveSession: (sessionId: string | null) => void;
  getActiveSession: () => ChatSession | null;

  // Legacy compatibility
  currentSession: SearchSession | null;
  setCurrentSession: (
    session: SearchSession | null,
  ) => void;
  addMessage: (message: ChatMessage) => void;
  addUserQuery: (query: string) => void;

  // UI
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
}

/**
 * Generate a unique client-side session ID.
 */
function generateSessionId(): string {
  return (
    Date.now().toString(36) +
    '-' +
    Math.random().toString(36).substring(2, 10)
  );
}

/**
 * Generate a short human-readable chat title.
 */
function generateTitle(query: string): string {
  const trimmed = query.trim();

  if (!trimmed) {
    return 'New Chat';
  }

  return trimmed.length > 50
    ? `${trimmed.substring(0, 50)}…`
    : trimmed;
}

/**
 * Current timestamp as an ISO string.
 */
function getUpdatedAt(): string {
  return new Date().toISOString();
}

/**
 * Convert canonical ChatSession into the SearchSession shape
 * expected by older components.
 *
 * Both session types use ISO timestamp strings.
 */
function toLegacySearchSession(
  session: ChatSession | null,
): SearchSession | null {
  if (!session) {
    return null;
  }

  return {
    id: session.id,
    title: session.title,
    query: session.query || '',
    messages: session.messages,
    createdAt: session.createdAt,
    updatedAt: session.updatedAt,
  };
}

/**
 * Build a new ChatSession.
 *
 * IMPORTANT:
 * session.id, the sessions map key, and activeSessionId
 * all use the same generated ID.
 */
function buildSession(query = ''): {
  sessionId: string;
  session: ChatSession;
} {
  const trimmed = query.trim();
  const sessionId = generateSessionId();
  const now = getUpdatedAt();

  const messages: ChatMessage[] = trimmed
    ? [
        {
          id: `${sessionId}-user`,
          role: 'user',
          content: trimmed,
          timestamp: new Date(),
        },
      ]
    : [];

  const session: SearchSession = {
    id: sessionId,
    title: trimmed
      ? generateTitle(trimmed)
      : 'New Chat',
    query: trimmed,
    messages,
    createdAt: now,
    updatedAt: now,
  };

  return {
    sessionId,
    session,
  };
}

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      // ============================================================
      // Sidebar
      // ============================================================

      activeView: 'home',

      setActiveView: (view) =>
        set({
          activeView: view,
        }),

      // ============================================================
      // Recent searches
      // ============================================================

      recentSearches: [],

      addRecentSearch: (query) =>
        set((state) => {
          const trimmed = query.trim();

          if (!trimmed) {
            return state;
          }

          const filtered =
            state.recentSearches.filter(
              (search) => search !== trimmed,
            );

          return {
            recentSearches: [
              trimmed,
              ...filtered,
            ].slice(0, 8),
          };
        }),

      /**
       * Start a NEW chat with the supplied initial query.
       */
      startSearch: (query: string) => {
        const trimmed = query.trim();

        if (!trimmed) {
          return '';
        }

        const { sessionId, session } =
          buildSession(trimmed);

        set((state) => ({
          activeView: 'search',
          activeSessionId: sessionId,

          sessions: {
            ...state.sessions,
            [sessionId]: session,
          },

          currentSession:
            toLegacySearchSession(session),
        }));

        get().addRecentSearch(trimmed);

        return sessionId;
      },

      // ============================================================
      // Items
      // ============================================================

      items: [],

      setItems: (items) =>
        set({
          items,
        }),

      mergeItems: (serverItems) =>
        set((state) => {
          const inFlightIds =
            state.inFlightMemoryIds;

          const localItems = state.items.filter(
            (item) => inFlightIds.has(item.id),
          );

          const serverItemsMap = new Map(
            serverItems.map((item) => [
              item.id,
              item,
            ]),
          );

          const merged = [...serverItems];

          for (const item of localItems) {
            if (!serverItemsMap.has(item.id)) {
              merged.unshift(item);
            }
          }

          return {
            items: merged,
          };
        }),

      addItem: (item) =>
        set((state) => ({
          items: [item, ...state.items],
        })),

      updateItem: (id, update) =>
        set((state) => ({
          items: state.items.map((item) =>
            item.id === id
              ? {
                  ...item,
                  ...update,
                }
              : item,
          ),
        })),

      deleteItem: (id) =>
        set((state) => ({
          items: state.items.filter(
            (item) => item.id !== id,
          ),
        })),

      // ============================================================
      // In-flight uploads
      // ============================================================

      inFlightMemoryIds: new Set<string>(),

      addInFlightMemory: (id) =>
        set((state) => ({
          inFlightMemoryIds: new Set(
            state.inFlightMemoryIds,
          ).add(id),
        })),

      removeInFlightMemory: (id) =>
        set((state) => {
          const next = new Set(
            state.inFlightMemoryIds,
          );

          next.delete(id);

          return {
            inFlightMemoryIds: next,
          };
        }),

      // ============================================================
      // Chat sessions
      // ============================================================

      sessions: {},

      activeSessionId: null,

      /**
       * Create a NEW chat with an initial query.
       */
      createSession: (query: string) => {
        const trimmed = query.trim();

        if (!trimmed) {
          return '';
        }

        const { sessionId, session } =
          buildSession(trimmed);

        set((state) => ({
          activeView: 'search',
          activeSessionId: sessionId,

          sessions: {
            ...state.sessions,
            [sessionId]: session,
          },

          currentSession:
            toLegacySearchSession(session),
        }));

        get().addRecentSearch(trimmed);

        return sessionId;
      },

      /**
       * Create an empty chat.
       */
      createEmptySession: () => {
        const { sessionId, session } =
          buildSession();

        set((state) => ({
          activeView: 'search',
          activeSessionId: sessionId,

          sessions: {
            ...state.sessions,
            [sessionId]: session,
          },

          currentSession: null,
        }));

        return sessionId;
      },

      /**
       * Append a message to a specific session.
       */
      addMessageToSession: (
        sessionId: string,
        message: ChatMessage,
      ) =>
        set((state) => {
          const session =
            state.sessions[sessionId];

          if (!session) {
            return state;
          }

          const normalizedMessage: ChatMessage = {
            ...message,
            id:
              message.id ||
              `${sessionId}-${Date.now()}-${Math.random()
                .toString(36)
                .substring(2, 7)}`,
            timestamp:
              message.timestamp || new Date(),
          };

          const updatedSession: ChatSession = {
            ...session,

            messages: [
              ...session.messages,
              normalizedMessage,
            ],

            updatedAt: getUpdatedAt(),
          };

          return {
            sessions: {
              ...state.sessions,
              [sessionId]: updatedSession,
            },

            currentSession:
              state.activeSessionId === sessionId
                ? toLegacySearchSession(
                    updatedSession,
                  )
                : state.currentSession,
          };
        }),

      /**
       * Update a session title.
       */
      updateSessionTitle: (
        sessionId: string,
        title: string,
      ) =>
        set((state) => {
          const session =
            state.sessions[sessionId];

          if (!session) {
            return state;
          }

          const updatedSession: ChatSession = {
            ...session,
            title:
              title.trim() || 'New Chat',
            updatedAt: getUpdatedAt(),
          };

          return {
            sessions: {
              ...state.sessions,
              [sessionId]: updatedSession,
            },

            currentSession:
              state.activeSessionId === sessionId
                ? toLegacySearchSession(
                    updatedSession,
                  )
                : state.currentSession,
          };
        }),

      /**
       * Delete a chat session.
       */
      deleteSession: (sessionId: string) =>
        set((state) => {
          const newSessions = {
            ...state.sessions,
          };

          delete newSessions[sessionId];

          if (
            state.activeSessionId !== sessionId
          ) {
            return {
              sessions: newSessions,
            };
          }

          const remainingIds =
            Object.keys(newSessions);

          if (remainingIds.length === 0) {
            return {
              sessions: newSessions,
              activeSessionId: null,
              activeView: 'home',
              currentSession: null,
            };
          }

          const nextSessionId =
            remainingIds[0];

          const nextSession =
            newSessions[nextSessionId];

          return {
            sessions: newSessions,
            activeSessionId: nextSessionId,
            activeView: 'search',
            currentSession:
              toLegacySearchSession(
                nextSession,
              ),
          };
        }),

      /**
       * Switch to an existing chat.
       */
      setActiveSession: (
        sessionId: string | null,
      ) =>
        set((state) => {
          if (!sessionId) {
            return {
              activeSessionId: null,
              activeView: 'home',
              currentSession: null,
            };
          }

          const session =
            state.sessions[sessionId];

          if (!session) {
            return {
              activeSessionId: null,
              activeView: 'home',
              currentSession: null,
            };
          }

          return {
            activeSessionId: sessionId,
            activeView: 'search',
            currentSession:
              toLegacySearchSession(session),
          };
        }),

      /**
       * Get the currently active canonical session.
       */
      getActiveSession: () => {
        const state = get();

        if (!state.activeSessionId) {
          return null;
        }

        return (
          state.sessions[
            state.activeSessionId
          ] || null
        );
      },

      // ============================================================
      // Legacy compatibility
      // ============================================================

      currentSession: null,

      /**
       * Compatibility bridge for older components.
       *
       * No Date conversion is performed because the actual
       * SearchSession timestamp fields are strings.
       */
      setCurrentSession: (session) =>
        set((state) => {
          if (!session) {
            return {
              currentSession: null,
            };
          }

          const existingSession =
            state.sessions[session.id];

          const chatSession: ChatSession =
            existingSession || {
              id: session.id,
              title: session.title || 'New Chat',
              query: session.query || '',
              messages: session.messages || [],
              createdAt: session.createdAt || getUpdatedAt(),
              updatedAt: session.updatedAt || getUpdatedAt(),
            };

          return {
            currentSession: session,

            activeSessionId:
              chatSession.id,

            sessions: {
              ...state.sessions,
              [chatSession.id]:
                chatSession,
            },
          };
        }),

      /**
       * Legacy message method.
       *
       * Redirects into the canonical active session.
       */
      addMessage: (message: ChatMessage) => {
        const state = get();

        if (!state.activeSessionId) {
          return;
        }

        state.addMessageToSession(
          state.activeSessionId,
          message,
        );
      },

      /**
       * Legacy user-query method.
       */
      addUserQuery: (query: string) => {
        const trimmed = query.trim();

        if (!trimmed) {
          return;
        }

        const state = get();

        if (!state.activeSessionId) {
          state.startSearch(trimmed);
          return;
        }

        const userMessage: ChatMessage = {
          id: `${Date.now()}-${Math.random()
            .toString(36)
            .substring(2, 7)}`,
          role: 'user',
          content: trimmed,
          timestamp: new Date(),
        };

        state.addMessageToSession(
          state.activeSessionId,
          userMessage,
        );

        state.addRecentSearch(trimmed);
      },

      // ============================================================
      // UI
      // ============================================================

      sidebarCollapsed: false,

      toggleSidebar: () =>
        set((state) => ({
          sidebarCollapsed:
            !state.sidebarCollapsed,
        })),
    }),

    {
      name: 'remora-store',

      partialize: (state) => ({
        recentSearches:
          state.recentSearches,

        items: state.items,

        // Persist actual conversations.
        sessions: state.sessions,
        activeSessionId:
          state.activeSessionId,

        sidebarCollapsed:
          state.sidebarCollapsed,

        // Deliberately do not persist:
        // - inFlightMemoryIds
        // - currentSession
        //
        // currentSession is only a compatibility
        // projection of sessions.
      }),
    },
  ),
);