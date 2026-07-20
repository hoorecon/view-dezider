/**
 * /tools/pros-cons — legacy simple Pros & Cons route.
 *
 * The simple two-column Pros & Cons mode has been retired (user request:
 * "remove the normal one, keep only 8-Step Pros & Cons"). This file now
 * serves as a thin redirect to the unified 8-Step Pros & Cons wizard so
 * any old bookmarks / shared links continue to work — preserving the
 * `id` query param so an in-flight analysis opens on the correct doc.
 */
import React from 'react';
import { Redirect, useLocalSearchParams } from 'expo-router';

export default function ProsConsRedirect() {
  const params = useLocalSearchParams<{ id?: string; module?: string }>();

  // Declarative <Redirect> instead of router.replace-in-useEffect: on a direct
  // deep-link the child effect fires BEFORE the Root Layout finishes mounting,
  // making expo-router throw "Attempted to navigate before mounting the Root
  // Layout component" (crashes to the NavErrorBoundary splash). <Redirect>
  // defers safely until the navigator is ready.
  const qs: string[] = [];
  if (params.id)     qs.push(`id=${encodeURIComponent(String(params.id))}`);
  qs.push(`module=${encodeURIComponent(String(params.module || 'pros-cons'))}`);
  return <Redirect href={`/tools/pros-cons-wizard?${qs.join('&')}` as any} />;
}

