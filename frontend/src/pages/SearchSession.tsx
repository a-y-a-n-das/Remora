import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, FileText } from 'lucide-react';
import { Button } from '../components/Button';
import { useAppStore } from '../store';
import { buildAssistantReply, mockItems } from '../data/mockData';

function DocThumbnail() {
  return (
    <div className="w-full h-full bg-[#dfe4f2] p-3 text-[#27324a]">
      <div className="h-full rounded-[3px] bg-[#f6f7fb] px-3 py-2 shadow-inner">
        <div className="text-[11px] font-bold tracking-tight">amazon.in</div>
        <div className="mt-2 h-px bg-[#b8c1d4]" />
        <div className="mt-2 grid grid-cols-2 gap-1">
          {[0, 1, 2, 3, 4, 5].map((index) => (
            <div key={index} className="h-1.5 rounded bg-[#c8cfdd]" />
          ))}
        </div>
        <div className="mt-3 space-y-1">
          {[80, 60, 72, 48].map((width) => (
            <div key={width} className="h-1 rounded bg-[#aeb8cc]" style={{ width: `${width}%` }} />
          ))}
        </div>
      </div>
    </div>
  );
}

function ResultCard({
  item,
  onClick,
}: {
  item: typeof mockItems[0];
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="w-[190px] flex-shrink-0 bg-[#0e172b]/80 border border-[#263657] rounded-xl overflow-hidden cursor-pointer transition-all hover:border-accent/50 hover:-translate-y-1 text-left"
    >
      <div className="relative h-[132px] overflow-hidden bg-[#172139]">
        {item.imageUrl ? (
          <img
            src={item.imageUrl}
            alt={item.name}
            className="w-full h-full object-cover"
          />
        ) : (
          <DocThumbnail />
        )}
      </div>

      <div className="p-3">
        <p className="text-sm font-medium text-text truncate">
          {item.name}
        </p>

        <p className="text-xs text-dim mt-1">
          {item.date}
        </p>
      </div>
    </button>
  );
}

function ItemPreview({
  item,
  onClose,
}: {
  item: typeof mockItems[0];
  onClose: () => void;
}) {
  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/90 backdrop-blur-sm"
        onClick={onClose}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: -20 }}
          className="relative max-w-4xl w-full max-h-[90vh] bg-gray-950 rounded-2xl border border-white/10 overflow-hidden flex flex-col"
          onClick={(event) => event.stopPropagation()}
        >
          {item.imageUrl ? (
            <img
              src={item.imageUrl}
              alt={item.name}
              className="w-full max-h-[70vh] object-contain"
            />
          ) : (
            <div className="aspect-video bg-gray-800 flex flex-col items-center justify-center gap-4">
              <FileText className="w-16 h-16 text-gray-500" />
              <span className="text-gray-500">
                PDF Document
              </span>
            </div>
          )}

          <div className="p-4 border-t border-white/10 flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-lg font-semibold text-white mb-1 truncate">
                {item.name}
              </p>

              <p className="text-sm text-gray-400">
                {item.type === 'document' ? 'Document' : 'Image'} ·{' '}
                {item.date}
              </p>
            </div>

            <button
              type="button"
              onClick={onClose}
              className="flex-shrink-0 px-4 py-2 bg-white/10 border border-white/20 rounded-lg text-gray-400 hover:bg-white/20 hover:text-white transition-colors"
            >
              Close
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

function MessageBubble({
  msg,
  onItemClick,
}: {
  msg: {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
    results?: typeof mockItems;
  };
  onItemClick: (item: typeof mockItems[0]) => void;
}) {
  const isUser = msg.role === 'user';

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex flex-col ${
        isUser ? 'items-end' : 'items-start'
      } gap-2 mb-6`}
    >
      <div className="text-xs text-dim font-medium">
        {isUser ? 'You' : 'Remora'}
      </div>

      <div
        className={`
          max-w-[520px] px-4 py-3 rounded-2xl
          ${
            isUser
              ? 'rounded-tr-xl rounded-bl-xl rounded-br-sm bg-accent/20 border border-accent/30'
              : 'rounded-tr-xl rounded-tl-xl rounded-br-sm bg-white/5 border border-white/10'
          }
        `}
      >
        <p className="text-text leading-relaxed">
          {msg.content}
        </p>
      </div>

      {msg.results && msg.results.length > 0 && (
        <div className="flex gap-4 flex-wrap max-w-[720px] mt-2">
          {msg.results.map((item) => (
            <ResultCard
              key={item.id}
              item={item}
              onClick={() => onItemClick(item)}
            />
          ))}
        </div>
      )}
    </motion.div>
  );
}

export function SearchSession({
  query: initialQuery,
}: {
  query: string;
}) {
  const {
    currentSession,
    setCurrentSession,
    addMessage,
    addRecentSearch,
  } = useAppStore();

  const [followUp, setFollowUp] = useState('');
  const [selectedItem, setSelectedItem] =
    useState<typeof mockItems[0] | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;
    if (currentSession?.query === initialQuery) {
      initialized.current = true;
      return;
    }

    initialized.current = true;

    const userMsg = {
      id: 'initial-user',
      role: 'user' as const,
      content: initialQuery,
      timestamp: new Date(),
    };

    const assistantMsg = buildAssistantReply(initialQuery);

    setCurrentSession({
      id: Date.now().toString(),
      query: initialQuery,
      messages: [userMsg, assistantMsg],
      createdAt: new Date(),
    });

    addRecentSearch(initialQuery);
  }, [
    initialQuery,
    currentSession?.query,
    setCurrentSession,
    addRecentSearch,
  ]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: 'smooth',
    });
  }, [currentSession?.messages?.length]);

  const handleSend = (event: React.FormEvent) => {
    event.preventDefault();

    const q = followUp.trim();

    if (!q) return;

    setFollowUp('');

    const userMsg = {
      id: `user-${Date.now()}`,
      role: 'user' as const,
      content: q,
      timestamp: new Date(),
    };

    const assistantMsg = buildAssistantReply(q);

    addMessage(userMsg);
    addMessage(assistantMsg);
    addRecentSearch(q);
  };

  const messages = currentSession?.messages ?? [];

  return (
    <div className="flex-1 h-full flex flex-col bg-bg">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 md:p-10">
        <div className="max-w-3xl mx-auto">
          {messages.map((msg) => (
            <MessageBubble
              key={msg.id}
              msg={msg}
              onItemClick={setSelectedItem}
            />
          ))}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Follow-up input */}
      <div className="border-t border-border/30 p-4 md:p-6 bg-bg/80 backdrop-blur-sm">
        <form
          onSubmit={handleSend}
          className="max-w-3xl mx-auto"
        >
          <div className="flex items-center gap-3 bg-white/5 border border-white/10 rounded-xl p-2 md:p-3">
            <input
              type="text"
              value={followUp}
              onChange={(event) =>
                setFollowUp(event.target.value)
              }
              placeholder="Ask a follow-up..."
              className="flex-1 bg-transparent text-text placeholder-muted text-base focus:outline-none"
            />

            <Button
              type="submit"
              disabled={!followUp.trim()}
            >
              <Send className="w-4 h-4" />
            </Button>
          </div>
        </form>
      </div>

      {/* Item preview */}
      {selectedItem && (
        <ItemPreview
          item={selectedItem}
          onClose={() => setSelectedItem(null)}
        />
      )}
    </div>
  );
}