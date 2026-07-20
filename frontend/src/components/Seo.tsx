/**
 * Seo — injects per-page <title>, meta description, canonical and
 * Open Graph / Twitter Card tags into the document <head>.
 *
 * Uses expo-router's <Head>, so the tags are baked into the prerendered HTML
 * during static web export (output: "static") — making the marketing & legal
 * pages index well and giving link-unfurlers/crawlers rich previews.
 *
 * Native is a no-op (head tags are web-only).
 */
import React from 'react';
import Head from 'expo-router/head';
import { Platform } from 'react-native';

// Canonical public origin of the deployed marketing site.
// Env-first (EXPO_PUBLIC_APP_URL, else EXPO_PUBLIC_BACKEND_URL same-origin),
// brand-site fallback kept only as last resort.
export const SITE_URL = (
  process.env.EXPO_PUBLIC_APP_URL ||
  process.env.EXPO_PUBLIC_BACKEND_URL ||
  'https://www.jelcos.ai'
).replace(/\/+$/, '');
const DEFAULT_IMAGE = `${SITE_URL}/og-image.png`;

type SeoProps = {
  title: string;
  description: string;
  path?: string;       // e.g. "/legal/privacy"
  image?: string;      // absolute URL
};

export default function Seo({ title, description, path = '/', image = DEFAULT_IMAGE }: SeoProps) {
  if (Platform.OS !== 'web') return null;
  const url = `${SITE_URL}${path}`;
  return (
    <Head>
      {/*
        NOTE: we deliberately do NOT render a <title> here. expo-router 6 static
        export can't serialize a Head <title>'s text, so it emits an EMPTY
        <title data-rh> that wins over the real brand <title> in app/+html.tsx
        (browsers use the first <title>) — which made the tab flash blank/"frontend".
        The per-page name is carried by og:title below; the brand <title> lives
        in +html and the client sets document.title in app/_layout.tsx.
      */}
      <meta name="description" content={description} />
      <link rel="canonical" href={url} />

      {/* Open Graph */}
      <meta property="og:type" content="website" />
      <meta property="og:site_name" content="JELCOS AI" />
      <meta property="og:title" content={title} />
      <meta property="og:description" content={description} />
      <meta property="og:url" content={url} />
      <meta property="og:image" content={image} />

      {/* Twitter */}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:title" content={title} />
      <meta name="twitter:description" content={description} />
      <meta name="twitter:image" content={image} />
    </Head>
  );
}
