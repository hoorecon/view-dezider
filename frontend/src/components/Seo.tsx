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
export const SITE_URL = 'https://www.jelcos.ai';
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
      <title>{title}</title>
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
