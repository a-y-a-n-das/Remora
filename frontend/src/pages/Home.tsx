import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { RemoraIcon } from '../components/Logo';
import { Input } from '../components/Input';
import { useAppStore } from '../store';

const suggestions = [
  'What did I spend on my recent purchases?',
  'What is the total amount on this receipt?',
  'When does my car insurance expire?',
  'What is my insurance policy number?',
  'What are the details of my upcoming trip?',
  'What is the booking or ticket number?',
  'What was the most recent payment I made?',
  'What are the important dates in my documents?',
  'Can you find my vehicle registration details?',
  'What did I buy recently?',
  'Find the details I need from my documents.',
];

export function Home() {
  const { startSearch } = useAppStore();
  const [query, setQuery] = useState('');
  const [suggIdx, setSuggIdx] = useState(0);
  const [suggKey, setSuggKey] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const timer = setInterval(() => {
      if (suggestions.length > 0) {
        setSuggIdx((i) => (i + 1) % suggestions.length);
        setSuggKey((k) => k + 1);
      }
    }, 3500);
    return () => clearInterval(timer);
  }, [suggestions.length]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const fillSuggestion = () => {
    if (suggestions.length === 0) return;
    setQuery(suggestions[suggIdx]);
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      startSearch(query.trim());
    }
  };

  return (
    <div className="flex-1 h-full flex flex-col">
      {/* Hero */}
      <div className="relative flex-1 flex flex-col items-center justify-center px-6">
        {/* Background image layer */}
        <div className="absolute inset-0 z-0 overflow-hidden">
          <img
            src="/assets/background.png"
            alt=""
            className="w-full h-full object-cover opacity-95"
            style={{ filter: 'brightness(0.88) contrast(1.04) saturate(0.98)' }}
          />
          <div className="absolute inset-0 bg-gradient-to-b from-[#050913]/38 via-[#050913]/8 to-[#050913]/34" />
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(3,7,18,0.08)_12%,rgba(3,7,18,0.28)_100%)]" />
          <div className="absolute inset-x-0 bottom-0 h-2/5 bg-gradient-to-t from-[#050913]/42 to-transparent" />
          <div className="absolute inset-y-0 left-0 w-1/6 bg-gradient-to-r from-[#050913]/90 to-transparent" />
          <div className="absolute inset-y-0 right-0 w-1/6 bg-gradient-to-l from-[#050913]/80 to-transparent" />
        </div>

        {/* Content */}
        <div className="relative z-10 w-full max-w-3xl mx-auto px-4 py-20 -translate-y-24 md:-translate-y-[8.5rem]">
          {/* Logo and title */}
          <div className="text-center mb-10 animate-fade-in">
            <RemoraIcon size={140} className="mx-auto -mb-5" />
            <h1 className="text-[2.75rem] leading-none font-bold text-white mb-4 tracking-tight">
              Remora
            </h1>
            <p className="text-[1.05rem] tracking-[0.12em] text-[#a9b7d6] font-light max-w-lg mx-auto text-center">
              Your visual knowledge, always at hand.
            </p>
          </div>

          {/* Search bar */}
          <form onSubmit={handleSearch} className="w-full max-w-[620px] mx-auto animate-slide-up">
            <div className="relative">
              <div className="relative">
                <div className="absolute inset-y-0 left-0 flex items-center pl-5 pointer-events-none">
                  <svg className="w-6 h-6 text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <circle cx="11" cy="11" r="8" stroke="currentColor" strokeWidth="2" />
                    <path d="M21 21l-4.35-4.35" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </div>
                <Input
                  ref={inputRef}
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSearch(e as unknown as React.FormEvent);
                    }
                  }}
                  placeholder="Search your collection..."
                  className="
                    w-full pl-[4.75rem] pr-16 py-[1.05rem]
                    bg-[#101b35]/60 backdrop-blur-md
                    border border-[#647bc2]/45 rounded-full
                    text-white placeholder-[#9aaad0] text-base
                    focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent/50
                    transition-all duration-200
                  "
                  autoComplete="off"
                  spellCheck={false}
                />
                <button
                  type="submit"
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 p-2.5 bg-[#5a73f4] rounded-full text-white shadow-[0_0_18px_rgba(90,115,244,0.4)] hover:bg-accent-h transition-colors"
                  aria-label="Search"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                  </svg>
                </button>
              </div>
            </div>
          </form>

          {/* Rotating suggestion */}
          <AnimatePresence mode="wait">
            <motion.div
              key={suggKey}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.3 }}
              className="mt-5 flex items-center justify-center animate-pulse-soft"
            >
              {suggestions.length > 0 && (
                <button
                  onClick={fillSuggestion}
                  className="text-sm text-white/85 italic cursor-pointer px-2 py-1 rounded hover:bg-white/5 transition-colors"
                  style={{ fontStyle: 'italic' }}
                >
                  {suggestions[suggIdx]}
                </button>
              )}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>

      {/* Tagline */}
      <div className="absolute bottom-6 right-8 z-10 pointer-events-none">
        <p className="text-xs text-dim text-right leading-relaxed">
          More than files.<br />
          A clearer you.
        </p>
      </div>
    </div>
  );
}