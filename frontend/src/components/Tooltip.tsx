/**
 * Cross-platform tooltip wrapper.
 *
 * Web: uses the native HTML `title` attribute (mouse-over tooltip) via
 *      the raw `dataSet` passthrough exposed by RN Web.
 * Native: renders a transparent long-press catcher — the caller is
 *         expected to also set `accessibilityLabel` for screen readers.
 *         (Long-press UX kept out of this helper to avoid pulling in a
 *         heavy popover library; consumers who want visible tooltips on
 *         mobile can wrap children in their own Popover.)
 *
 * Usage:
 *   <Tooltip text="Save as Template">
 *     <TouchableOpacity ...>...</TouchableOpacity>
 *   </Tooltip>
 */
import React from 'react';
import { Platform, View } from 'react-native';

interface TooltipProps {
  text: string;
  children: React.ReactNode;
  style?: any;
}

export default function Tooltip({ text, children, style }: TooltipProps) {
  if (Platform.OS === 'web') {
    // On web, render a native <span title="..."> so browsers show the
    // system tooltip on hover. React-Native-Web treats unknown DOM
    // props on `View` inconsistently, so we use a real span here.
    return (
      // @ts-ignore — intentional raw HTML on web
      <span title={text} style={{ display: 'inline-flex' }}>
        {children}
      </span>
    );
  }
  return <View style={style}>{children}</View>;
}
