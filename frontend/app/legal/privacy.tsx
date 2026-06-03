import React from 'react';
import LegalShell from '../../src/components/marketing/LegalShell';
import { PRIVACY_POLICY } from '../../src/constants/company';

export default function PrivacyPage() {
  return <LegalShell doc={PRIVACY_POLICY} />;
}
