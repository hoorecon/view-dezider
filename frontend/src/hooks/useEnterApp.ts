import { useCallback, useRef, useState } from 'react';
import { useFocusEffect, useNavigation } from 'expo-router';

const LOADER_MS = 1500;

/**
 * After a successful login/signup, show the JELCOS loader briefly and then
 * navigate. Repeat calls are ignored because auth screens trigger navigation
 * from both the submit handler and the isAuthenticated effect.
 *
 * The pending navigation is dropped once this screen loses focus: another
 * screen (e.g. the landing page underneath) may already have moved the user
 * on, and firing late would yank them out of whatever they opened next.
 */
export function useEnterApp(router: any) {
  const navigation = useNavigation();
  const [entering, setEntering] = useState(false);
  const started = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useFocusEffect(useCallback(() => () => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  }, []));

  const enterApp = useCallback((route: string) => {
    if (started.current) return;
    started.current = true;
    setEntering(true);
    timer.current = setTimeout(() => {
      timer.current = null;
      if (navigation.isFocused()) router.replace(route as any);
    }, LOADER_MS);
  }, [router, navigation]);

  return { entering, enterApp };
}
