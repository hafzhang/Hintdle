// JSON-LD builders. Every page ships at least BreadcrumbList; tool pages add
// WebApplication and/or FAQPage.
import { SITE, abs } from './site';

export function breadcrumbLd(items: { name: string; path: string }[]) {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((it, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      name: it.name,
      item: abs(it.path),
    })),
  };
}

export function webApplicationLd(opts: { name: string; path: string; description: string }) {
  return {
    '@context': 'https://schema.org',
    '@type': 'WebApplication',
    name: opts.name,
    url: abs(opts.path),
    description: opts.description,
    applicationCategory: 'GameApplication',
    operatingSystem: 'Any (web browser)',
    browserRequirements: 'Requires JavaScript for the interactive solver.',
    offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' },
    isAccessibleForFree: true,
    publisher: { '@type': 'Organization', name: SITE.name, url: SITE.url },
  };
}

export function faqLd(qas: { q: string; a: string }[]) {
  return {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: qas.map((qa) => ({
      '@type': 'Question',
      name: qa.q,
      acceptedAnswer: { '@type': 'Answer', text: qa.a },
    })),
  };
}

export function articleLd(opts: {
  headline: string;
  description: string;
  path: string;
  datePublished: string;
  dateModified: string;
}) {
  return {
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: opts.headline,
    description: opts.description,
    mainEntityOfPage: abs(opts.path),
    datePublished: opts.datePublished,
    dateModified: opts.dateModified,
    publisher: { '@type': 'Organization', name: SITE.name, url: SITE.url },
  };
}

/** Sitewide publisher node — emitted on every page alongside the page-level data. */
export function organizationLd() {
  return {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: SITE.name,
    url: SITE.url,
    logo: { '@type': 'ImageObject', url: abs(SITE.logo), width: 512, height: 512 },
    description:
      'Independent reference site for the daily four-letter word ladder: answers, spoiler-free hints and a shortest-path solver.',
  };
}

/** Sitewide site node — pairs with organizationLd(). */
export function webSiteLd() {
  return {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: SITE.name,
    url: SITE.url,
    inLanguage: 'en',
    description:
      'Daily answers, four levels of spoiler-free hints and a shortest-path solver for the four-letter word ladder.',
    publisher: { '@type': 'Organization', name: SITE.name, url: SITE.url },
  };
}
