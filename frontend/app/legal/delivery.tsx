import React from 'react';
import LegalShell from '../../src/components/marketing/LegalShell';
import { DELIVERY_POLICY } from '../../src/constants/company';

export default function DeliveryPolicyPage() {
  return <LegalShell doc={DELIVERY_POLICY} />;
}
