import React from 'react';
import LegalShell from '../../src/components/marketing/LegalShell';
import { REFUND_POLICY } from '../../src/constants/company';

export default function RefundPolicyPage() {
  return <LegalShell doc={REFUND_POLICY} />;
}
