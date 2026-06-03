/**
 * Company / product information and legal-page content.
 * Single source of truth for the public marketing + legal pages.
 *
 * Legal entity (Razorpay merchant): HOORECON IT-Sys Pvt Ltd
 * Product: JELCOS AI
 */

export const COMPANY = {
  product: 'JELCOS AI',
  tagline: "Joyful Executive's Life Choices Operating System — Powered by AI",
  legalName: 'HOORECON IT-Sys Pvt Ltd',
  website: 'www.hoorecon.com',
  websiteUrl: 'https://www.hoorecon.com',
  email: 'admin@hoorecon.com',
  phone: '+(91)-(0)44-46972104',
  phoneDial: '+914446972104',
  addressLines: [
    'Innov8 Millenia, 2nd Floor, East Wing, RMZ,',
    'Millennia Business Park, Campus 1A, No. 143,',
    'MGR Road (North Veeranam Salai), Perungudi,',
    'Sholinganallur, Chennai-600096, Tamil Nadu, India.',
  ],
  addressShort: 'Perungudi, Sholinganallur, Chennai-600096, Tamil Nadu, India.',
  jurisdiction: 'Chennai, Tamil Nadu, India',
  lastUpdated: '03 June 2026',
};

export const LEGAL_LINKS = [
  { label: 'Delivery Policy', route: '/legal/delivery' },
  { label: 'Refund & Cancellation Policy', route: '/legal/refund' },
  { label: 'Terms of Use', route: '/legal/terms' },
  { label: 'Privacy Policy', route: '/legal/privacy' },
  { label: 'Contact Us', route: '/contact' },
] as const;

export type LegalSection = {
  heading?: string;
  paragraphs?: string[];
  bullets?: string[];
};

export type LegalDoc = {
  title: string;
  intro?: string;
  sections: LegalSection[];
};

// ───────────────────────── Privacy Policy ─────────────────────────
export const PRIVACY_POLICY: LegalDoc = {
  title: 'Privacy Policy',
  intro:
    `${COMPANY.legalName} ("we", "us", "our") operates the ${COMPANY.product} application and related ` +
    `services (the "Service"). This Privacy Policy explains what information we collect, how we use it, ` +
    `and the choices you have. By using the Service you agree to the practices described here.`,
  sections: [
    {
      heading: '1. Information We Collect',
      bullets: [
        'Account information: name, email address, and password (stored as a secure hash).',
        'Decision & content data: the decisions, factors, goals, notes, action plans and other content you create in the app.',
        'Payment information: when you purchase a subscription or credits, payments are processed by our payment gateway (Razorpay). We do not store your full card or banking details on our servers.',
        'Usage data: device type, browser, log data and feature usage, collected to operate and improve the Service.',
        'Communications: messages you send us for support or enquiries.',
      ],
    },
    {
      heading: '2. How We Use Your Information',
      bullets: [
        'To provide, maintain and improve the Service and its decision-support features.',
        'To process payments, manage subscriptions and deliver purchased credits or plans.',
        'To personalise your experience and generate AI-assisted suggestions you request.',
        'To respond to your support requests and send service-related notifications.',
        'To ensure security, prevent fraud and comply with legal obligations.',
      ],
    },
    {
      heading: '3. Third-Party Service Providers',
      paragraphs: [
        'We share limited data with trusted providers only to the extent needed to run the Service. These include payment processing (Razorpay), cloud hosting and infrastructure, and AI model providers that power optional AI features. These providers are bound to use the data only to perform services for us.',
      ],
    },
    {
      heading: '4. Data Security',
      paragraphs: [
        'We use industry-standard administrative, technical and physical safeguards — including encrypted transport (HTTPS) and hashed credentials — to protect your information. No method of transmission or storage is 100% secure, but we work continuously to protect your data.',
      ],
    },
    {
      heading: '5. Data Retention',
      paragraphs: [
        'We retain your account and content data for as long as your account is active or as needed to provide the Service. You may request deletion of your account and associated data at any time by contacting us.',
      ],
    },
    {
      heading: '6. Your Rights',
      bullets: [
        'Access, update or correct your personal information from within the app.',
        'Request a copy or deletion of your data by emailing us.',
        'Withdraw consent or close your account at any time.',
      ],
    },
    {
      heading: '7. Cookies',
      paragraphs: [
        'On the web, we use essential cookies and local storage to keep you signed in and remember your preferences. Disabling these may affect core functionality.',
      ],
    },
    {
      heading: "8. Children's Privacy",
      paragraphs: [
        'The Service is not intended for individuals under the age of 18. We do not knowingly collect data from children.',
      ],
    },
    {
      heading: '9. Changes to This Policy',
      paragraphs: [
        'We may update this Privacy Policy from time to time. Material changes will be reflected by updating the "Last updated" date on this page.',
      ],
    },
    {
      heading: '10. Contact Us',
      paragraphs: [
        `If you have questions about this Privacy Policy or your data, contact ${COMPANY.legalName} at ${COMPANY.email} or ${COMPANY.phone}.`,
      ],
    },
  ],
};

// ───────────────────────── Terms of Use ─────────────────────────
export const TERMS_OF_USE: LegalDoc = {
  title: 'Terms of Use',
  intro:
    `These Terms of Use ("Terms") govern your access to and use of the ${COMPANY.product} application and ` +
    `services operated by ${COMPANY.legalName}. By creating an account or using the Service, you agree to these Terms.`,
  sections: [
    {
      heading: '1. Eligibility & Account',
      paragraphs: [
        'You must be at least 18 years old to use the Service. You are responsible for maintaining the confidentiality of your account credentials and for all activity under your account.',
      ],
    },
    {
      heading: '2. Licence to Use',
      paragraphs: [
        'Subject to these Terms, we grant you a limited, non-exclusive, non-transferable, revocable licence to use the Service for your personal or internal business decision-making purposes.',
      ],
    },
    {
      heading: '3. Acceptable Use',
      bullets: [
        'Do not misuse, reverse-engineer, or attempt to gain unauthorised access to the Service.',
        'Do not upload unlawful, infringing, or harmful content.',
        'Do not use the Service in any way that could disable, overburden, or impair it.',
      ],
    },
    {
      heading: '4. Subscriptions, Credits & Payments',
      paragraphs: [
        'The Service offers paid subscription plans (billed on a recurring basis) and one-time purchases of credits. Prices are displayed in the app at the time of purchase. Payments are processed securely through Razorpay.',
        'Subscriptions renew automatically until cancelled. You can cancel at any time to stop future billing; access continues until the end of the current paid period. Please review our Refund & Cancellation Policy for details.',
      ],
    },
    {
      heading: '5. AI-Generated Content',
      paragraphs: [
        'Certain features use AI to generate suggestions and analysis. These outputs are for informational support only and do not constitute professional, financial, legal, or medical advice. You remain solely responsible for your decisions.',
      ],
    },
    {
      heading: '6. Intellectual Property',
      paragraphs: [
        `All rights, title and interest in the Service — including software, design and trademarks such as "${COMPANY.product}" — are owned by ${COMPANY.legalName}. Content you create remains yours.`,
      ],
    },
    {
      heading: '7. Disclaimers & Limitation of Liability',
      paragraphs: [
        'The Service is provided "as is" without warranties of any kind. To the maximum extent permitted by law, we are not liable for any indirect, incidental, or consequential damages arising from your use of the Service.',
      ],
    },
    {
      heading: '8. Termination',
      paragraphs: [
        'We may suspend or terminate access if you breach these Terms. You may stop using the Service and request account deletion at any time.',
      ],
    },
    {
      heading: '9. Governing Law',
      paragraphs: [
        `These Terms are governed by the laws of India, and any disputes are subject to the exclusive jurisdiction of the courts of ${COMPANY.jurisdiction}.`,
      ],
    },
    {
      heading: '10. Contact',
      paragraphs: [
        `Questions about these Terms? Contact ${COMPANY.legalName} at ${COMPANY.email}.`,
      ],
    },
  ],
};

// ──────────────── Refund & Cancellation Policy ────────────────
export const REFUND_POLICY: LegalDoc = {
  title: 'Refund & Cancellation Policy',
  intro:
    `This policy explains cancellations and refunds for purchases made on ${COMPANY.product}, operated by ${COMPANY.legalName}.`,
  sections: [
    {
      heading: '1. No Refunds',
      paragraphs: [
        'All payments for subscription plans and one-time credit purchases are non-refundable. Once a payment is successfully processed and access/credits are delivered, the amount paid cannot be refunded, except where required by applicable law.',
      ],
    },
    {
      heading: '2. Cancelling a Subscription',
      bullets: [
        'You may cancel your subscription at any time from your account settings within the app, or by emailing us.',
        'Cancellation stops all future billing. No further charges will be made after you cancel.',
        'Your plan benefits remain active until the end of the current paid billing period; the subscription is not renewed thereafter.',
      ],
    },
    {
      heading: '3. One-Time Credits',
      paragraphs: [
        'Credits purchased on a one-time basis are delivered to your account immediately upon successful payment and are non-refundable once delivered.',
      ],
    },
    {
      heading: '4. Failed or Duplicate Payments',
      paragraphs: [
        'If you were charged but did not receive access or credits, or if you were charged more than once for the same purchase, please contact us within 7 days with your payment reference. We will investigate and, where a verified duplicate or erroneous charge is found, reverse it.',
      ],
    },
    {
      heading: '5. How to Reach Us',
      paragraphs: [
        `For cancellations or payment queries, email ${COMPANY.email} or call ${COMPANY.phone}. Please include your registered email and payment reference.`,
      ],
    },
  ],
};

// ───────────────────────── Delivery Policy ─────────────────────────
export const DELIVERY_POLICY: LegalDoc = {
  title: 'Delivery Policy',
  intro:
    `${COMPANY.product} is a digital software service provided by ${COMPANY.legalName}. There is no physical ` +
    `shipment of goods. This policy explains how access to paid features is delivered.`,
  sections: [
    {
      heading: '1. Digital Delivery',
      paragraphs: [
        'Access to purchased subscription plans and credits is granted instantly, and in all cases within 24 hours, of a successful payment — directly to your registered app account. No physical product is shipped.',
      ],
    },
    {
      heading: '2. Accessing Your Purchase',
      bullets: [
        'Sign in to your account on the web or mobile app using your registered email.',
        'Your active plan and available credits are reflected automatically in your account.',
        'For subscriptions, premium features unlock immediately for the duration of your billing period.',
      ],
    },
    {
      heading: '3. Delivery Issues',
      paragraphs: [
        `If your purchase is not reflected in your account within 24 hours of a successful payment, please contact us at ${COMPANY.email} with your registered email and payment reference, and we will resolve it promptly.`,
      ],
    },
  ],
};

export const LEGAL_DOCS: Record<string, LegalDoc> = {
  privacy: PRIVACY_POLICY,
  terms: TERMS_OF_USE,
  refund: REFUND_POLICY,
  delivery: DELIVERY_POLICY,
};
