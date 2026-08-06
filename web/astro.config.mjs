import { defineConfig } from 'astro/config';
import react from '@astrojs/react';

// Static output: the deployable artifact is nginx + a folder of files, and the
// browser fetches /api at runtime — so a nightly ingest changes what visitors
// see without rebuilding the image.
export default defineConfig({
  site: 'https://elcourtside.sstathatos.dev',
  integrations: [react()],
  vite: {
    server: {
      // Dev mirrors production: code always calls same-origin /api. In the
      // cluster the ingress routes it; here Vite does.
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
        },
      },
    },
  },
});
