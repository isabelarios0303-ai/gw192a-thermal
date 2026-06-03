import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: 'class',
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Dark medical dashboard palette
        bg: { DEFAULT: '#0b1020', soft: '#111831', card: '#151d38' },
        accent: { DEFAULT: '#38bdf8', muted: '#0ea5e9' },
        ok: '#22c55e',
        warn: '#f59e0b',
        crit: '#ef4444',
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
};

export default config;
