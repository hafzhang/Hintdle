import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

// hintdle — static export, deployed to Cloudflare Pages.
// Data build (data/processed + data/daily) is the single source of truth; pages only read it.
export default defineConfig({
  site: 'https://hintdle.com',
  output: 'static',
  trailingSlash: 'always',
  build: {
    // inline small stylesheets so the first paint needs zero extra round-trips
    inlineStylesheets: 'always',
  },
  integrations: [
    sitemap({
      // /archive/page/N/ carries noindex, so it must stay out of the sitemap too.
      filter: (page) => !page.includes('/404') && !page.includes('/archive/page/'),
    }),
  ],
});
