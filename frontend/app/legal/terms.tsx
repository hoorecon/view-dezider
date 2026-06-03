import React from 'react';
import LegalShell from '../../src/components/marketing/LegalShell';
import { TERMS_OF_USE } from '../../src/constants/company';

export default function TermsPage() {
  return <LegalShell doc={TERMS_OF_USE} />;
}
