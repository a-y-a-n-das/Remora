/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: '#0B1120',
        'bg-sidebar': '#090D1A',
        'bg-card': '#111827',
        border: 'rgba(255,255,255,0.07)',
        accent: '#4361EE',
        'accent-h': '#5A74F0',
        text: '#E8EDF8',
        muted: '#6B7A99',
        dim: '#4A5A7A',
        success: '#10B981',
        error: '#EF4444',
        warning: '#F59E0B',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        'glow': '0 0 0 1px rgba(67,97,238,0.08), 0 4px 28px rgba(0,0,0,0.35)',
        'glow-hover': '0 0 0 1px rgba(67,97,238,0.15), 0 8px 40px rgba(0,0,0,0.4)',
      },
      backgroundImage: {
        'home-gradient': 'radial-gradient(ellipse 90% 55% at 55% 18%, rgba(67,97,238,0.18) 0%, transparent 65%), radial-gradient(ellipse 50% 35% at 80% 5%, rgba(100,140,255,0.10) 0%, transparent 50%)',
        'search-gradient': 'radial-gradient(ellipse 70% 40% at 50% 0%, rgba(67,97,238,0.1) 0%, transparent 60%)',
      },
    },
  },
  plugins: [],
}