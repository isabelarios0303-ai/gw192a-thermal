/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Static export so the PWA can be hosted on any static host (Netlify, GitHub Pages, etc.).
  // The deployed site runs the in-browser demo when no backend is reachable (see src/lib/ws.ts).
  output: 'export',
  images: { unoptimized: true },
  env: {
    NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000',
    NEXT_PUBLIC_WS_BASE: process.env.NEXT_PUBLIC_WS_BASE || 'ws://localhost:8000',
    NEXT_PUBLIC_DEMO: process.env.NEXT_PUBLIC_DEMO || '',
  },
};

module.exports = nextConfig;
