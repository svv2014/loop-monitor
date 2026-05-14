import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  base: '/',
  build: {
    outDir: '../static/dist',
    emptyOutDir: true,
    // ES2022 → top-level await is supported (used by src/lib/fixtures.ts to
    // load the fixture payload at module init).
    target: 'es2022',
  },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:18792',
    },
  },
});
