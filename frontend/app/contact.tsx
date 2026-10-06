/**
 * Old /contact address. The booking form now lives on the main page.
 */
import { useEffect } from 'react';
import { Platform } from 'react-native';
import { useRouter } from 'expo-router';

export default function ContactPage() {
  const router = useRouter();
  useEffect(() => {
    if (Platform.OS === 'web' && typeof window !== 'undefined') {
      window.location.replace('/#demo');
      return;
    }
    router.replace('/#demo' as any);
  }, [router]);
  return null;
}
