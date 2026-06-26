// @ts-nocheck
import { ScrollViewStyleReset } from "expo-router/html";
import type { PropsWithChildren } from "react";

export default function Root({ children }: PropsWithChildren) {
  return (
    <html lang="en" style={{ height: "100%" }}>
      <head>
        <meta charSet="utf-8" />
        <meta httpEquiv="X-UA-Compatible" content="IE=edge" />
        {/*
          Brand-level <title> fallback for every static page. Per-page SEO is
          provided by <Seo> (expo-router <Head>): it serializes meta description,
          canonical and Open Graph / Twitter tags (incl. per-page og:title) into
          the prerendered HTML. NOTE: expo-router 6 SSG does NOT serialize a
          per-page <title> tag, so og:title carries the per-page title for
          crawlers/social; the client also sets document.title per route
          (app/_layout.tsx). Description is intentionally NOT set here to avoid a
          duplicate with <Seo>.
        */}
        {/*
          The brand <title> is provided once, at the root, via <Head> in
          app/_layout.tsx — it serializes into the static HTML as the first
          <title>. Do NOT set a <title> here (or in page-level <Seo>), else
          expo-router emits a duplicate/empty <title> that wins in the browser
          and shows a blank/app-name tab while loading. Per-page name is carried
          by og:title; the client keeps document.title in sync.
        */}
        <meta
          name="viewport"
          content="width=device-width, initial-scale=1, shrink-to-fit=no"
        />
        {/*
          Disable body scrolling on web to make ScrollView components work correctly.
          If you want to enable scrolling, remove `ScrollViewStyleReset` and
          set `overflow: auto` on the body style below.
        */}
        <ScrollViewStyleReset />
        <style
          dangerouslySetInnerHTML={{
            __html: `
              body > div:first-child { position: fixed !important; top: 0; left: 0; right: 0; bottom: 0; }
              [role="tablist"] [role="tab"] * { overflow: visible !important; }
              [role="heading"], [role="heading"] * { overflow: visible !important; }
            `,
          }}
        />
      </head>
      <body
        style={{
          margin: 0,
          height: "100%",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {children}
      </body>
    </html>
  );
}
