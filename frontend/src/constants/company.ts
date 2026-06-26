/**
 * Company / product information and legal-page content.
 *
 * The values below are the DEFAULTS / fallbacks. At runtime they are overridden
 * by the Admin-configured company profile (GET /api/appearance), surfaced via
 * the `useCompany()` hook. Legal/contact pages build their text from a passed
 * `CompanyInfo` object so a change in Admin instantly reflects everywhere.
 *
 * Legal entity (Razorpay merchant): HOORECON IT-Sys Pvt Ltd
 * Product: JELCOS AI
 */

export type CompanyInfo = {
  product: string;
  tagline: string;
  legalName: string;
  website: string;          // merchant website (the product site Razorpay checks)
  websiteUrl: string;
  companyWebsite: string;   // corporate website
  companyWebsiteUrl: string;
  email: string;
  phone: string;
  phoneDial: string;
  addressLines: string[];
  addressShort: string;
  jurisdiction: string;
  lastUpdated: string;
  supportHours: string;
  businessType: string;
  description: string;
  paymentGateway: string;
};

export const COMPANY: CompanyInfo = {
  product: 'JELCOS AI',
  tagline: "Joyful Executive's Life Choices Operating System — Powered by AI",
  legalName: 'HOORECON IT-Sys Private Limited',
  website: 'www.jelcos.ai',
  websiteUrl: 'https://www.jelcos.ai',
  companyWebsite: 'www.hoorecon.com',
  companyWebsiteUrl: 'https://www.hoorecon.com',
  email: 'support@hoorecon.com',
  phone: '044 4697 2104',
  phoneDial: '04446972104',
  addressLines: [
    'Innov8 Millenia, 2nd Floor, East Wing, RMZ,',
    'Millennia Business Park, Campus 1A, No. 143,',
    'MGR Road (North Veeranam Salai), Perungudi,',
    'Sholinganallur, Chennai-600096, Tamil Nadu, India.',
  ],
  addressShort: 'Perungudi, Sholinganallur, Chennai-600096, Tamil Nadu, India.',
  jurisdiction: 'Chennai, Tamil Nadu, India',
  lastUpdated: '26 June 2026',
  supportHours: 'Monday to Saturday, 10:00 AM to 6:00 PM IST',
  businessType: 'Online digital learning, decision-support reports, subscriptions and coaching services.',
  description:
    'HOORECON IT-Sys Private Limited provides online digital learning, decision-support reports, ' +
    'subscriptions and coaching services. Customers purchase access to digital tools, reports, ' +
    'training content and guided advisory sessions through the website.',
  paymentGateway: 'Razorpay',
};

export const LEGAL_LINKS = [
  { label: 'Terms & Conditions', route: '/legal/terms' },
  { label: 'Privacy Policy', route: '/legal/privacy' },
  { label: 'Refund Policy', route: '/legal/refund' },
  { label: 'Cancellation Policy', route: '/legal/cancellation' },
  { label: 'Delivery Policy', route: '/legal/delivery' },
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
const privacyPolicy = (c: CompanyInfo): LegalDoc => ({
  title: 'Privacy Policy',
  intro:
    `${c.legalName} ("we", "us", "our") operates the ${c.product} website and related ` +
    `services at ${c.websiteUrl} (the "Service"). ${c.description} This Privacy Policy explains ` +
    `what information we collect, how we use it, and the choices you have. By using the Service ` +
    `you agree to the practices described here.`,
  sections: [
    {
      heading: '1. Information We Collect',
      bullets: [
        'Account information: name, email address, and password (stored as a secure hash).',
        'Content data: the decisions, factors, goals, notes, reports, action plans and other content you create or request in the Service.',
        'Payment information: limited transaction details required to process and confirm payments through our payment gateway.',
        'Usage data: device type, browser, log data and feature usage, collected to operate and improve the Service.',
        'Communications: messages you send us for support or enquiries.',
      ],
    },
    {
      heading: '2. Purpose of Data Collection',
      bullets: [
        'To provide, maintain and improve the Service and its decision-support, learning and coaching features.',
        'To process payments, manage subscriptions and deliver purchased digital services, reports or credits.',
        'To personalise your experience and generate the analyses, reports and guidance you request.',
        'To respond to your support requests and send service-related communications.',
        'To ensure security, prevent fraud and comply with legal obligations.',
      ],
    },
    {
      heading: '3. Account and Subscription Data',
      paragraphs: [
        'When you create an account or purchase a subscription or credits, we store the information needed to manage your account, your active plan, your purchase history and the digital services delivered to you. This data is used solely to operate your account and deliver the Service.',
      ],
    },
    {
      heading: '4. Payment Processing through Razorpay',
      paragraphs: [
        'Payments are processed through Razorpay. We do not store full card numbers, CVV, UPI PIN, netbanking credentials or complete banking details on our servers.',
        'Razorpay processes your payment information under its own privacy and security standards (PCI-DSS compliant). We receive only the limited transaction status and reference details needed to confirm and reconcile your purchase.',
      ],
    },
    {
      heading: '5. Data Sharing with Service Providers',
      paragraphs: [
        'We share limited data with trusted providers only to the extent needed to run the Service. These include payment processing (Razorpay), cloud hosting and infrastructure, communication/email delivery, and AI model providers that power optional analysis features. These providers are bound to use the data only to perform services for us and not for their own purposes. We do not sell your personal data.',
      ],
    },
    {
      heading: '6. Cookies and Analytics',
      paragraphs: [
        'On the web, we use essential cookies and local storage to keep you signed in and remember your preferences, and limited analytics to understand feature usage and improve the Service. Disabling essential cookies may affect core functionality.',
      ],
    },
    {
      heading: '7. Data Security',
      paragraphs: [
        'We use industry-standard administrative, technical and physical safeguards — including encrypted transport (HTTPS) and hashed credentials — to protect your information. No method of transmission or storage is 100% secure, but we work continuously to protect your data.',
      ],
    },
    {
      heading: '8. Data Retention',
      paragraphs: [
        'We retain your account and content data for as long as your account is active or as needed to provide the Service and meet legal, accounting or reporting requirements. You may request deletion of your account and associated data at any time by contacting us.',
      ],
    },
    {
      heading: '9. User Rights and Contact',
      bullets: [
        'Access, update or correct your personal information from within the app.',
        'Request a copy or deletion of your data by emailing us.',
        'Withdraw consent or close your account at any time.',
      ],
    },
    {
      heading: '10. Contact Information',
      paragraphs: [
        `If you have questions about this Privacy Policy or your data, contact ${c.legalName} at ${c.email} or ${c.phone}.`,
        `Registered/Operating Address: ${c.addressLines.join(' ')}`,
      ],
    },
  ],
});

// ───────────────────────── Terms of Use ─────────────────────────
const termsOfUse = (c: CompanyInfo): LegalDoc => ({
  title: 'Terms & Conditions',
  intro:
    `These Terms & Conditions ("Terms") govern your access to and use of the ${c.product} website ` +
    `(${c.websiteUrl}) and services operated by ${c.legalName}. By creating an account or using the ` +
    `Service, you agree to these Terms.`,
  sections: [
    {
      heading: '1. About HOORECON IT-Sys Private Limited',
      paragraphs: [
        `${c.legalName} is the company that owns and operates ${c.product} at ${c.websiteUrl}. ${c.description}`,
      ],
    },
    {
      heading: '2. Nature of Services',
      paragraphs: [
        'We provide online digital learning, decision-support reports, subscriptions and coaching services. All services are digital and are delivered electronically through the website, user dashboard, email or scheduled online sessions.',
      ],
    },
    {
      heading: '3. User Account and Access',
      paragraphs: [
        'You must be at least 18 years old to use the Service. You are responsible for maintaining the confidentiality of your account credentials and for all activity under your account.',
      ],
    },
    {
      heading: '4. Subscription Plans and Credits',
      paragraphs: [
        'The Service offers paid subscription plans (billed on a recurring basis) and one-time purchases of credits. Prices are displayed on the website at the time of purchase. Subscriptions renew automatically until cancelled; you can cancel at any time to stop future billing.',
      ],
    },
    {
      heading: '5. Payment Terms',
      paragraphs: [
        `All payments are processed securely through ${c.paymentGateway}. By making a purchase you authorise us and ${c.paymentGateway} to charge the applicable amount to your chosen payment method. Taxes, where applicable, are charged as per law.`,
      ],
    },
    {
      heading: '6. Delivery of Digital Services',
      paragraphs: [
        'After successful payment confirmation, access to digital tools, reports, subscriptions, training content or guided advisory sessions is provided electronically. Please refer to our Delivery Policy for details.',
      ],
    },
    {
      heading: '7. Cancellation and Refund Reference',
      paragraphs: [
        'Cancellations are governed by our Cancellation Policy and refunds by our Refund Policy. Please review both before purchasing.',
      ],
    },
    {
      heading: '8. User Responsibilities',
      bullets: [
        'Provide accurate account and payment information.',
        'Do not misuse, reverse-engineer, or attempt to gain unauthorised access to the Service.',
        'Do not upload unlawful, infringing, or harmful content, or use the Service in any way that could disable, overburden or impair it.',
      ],
    },
    {
      heading: '9. Decision-Support Disclaimer',
      paragraphs: [
        'Our services are intended for education, self-reflection, decision-support and coaching purposes only. We do not guarantee any specific personal, professional, financial, legal, medical, relationship or life outcome. Users are responsible for their final decisions.',
      ],
    },
    {
      heading: '10. No Guarantee of Outcomes',
      paragraphs: [
        'Any analysis, report, suggestion or guidance provided through the Service is informational support only and does not constitute professional, financial, legal or medical advice. We make no warranty that the Service will produce any particular result.',
      ],
    },
    {
      heading: '11. Intellectual Property',
      paragraphs: [
        `All rights, title and interest in the Service — including software, design, content and trademarks such as "${c.product}" — are owned by ${c.legalName}. Content you create remains yours.`,
      ],
    },
    {
      heading: '12. Limitation of Liability',
      paragraphs: [
        'The Service is provided "as is" without warranties of any kind. To the maximum extent permitted by law, we are not liable for any indirect, incidental, special or consequential damages arising from your use of the Service.',
      ],
    },
    {
      heading: '13. Governing Law and Jurisdiction',
      paragraphs: [
        `These Terms are governed by the laws of India, and any disputes are subject to the exclusive jurisdiction of the courts of ${c.jurisdiction}.`,
      ],
    },
    {
      heading: '14. Contact Information',
      paragraphs: [
        `${c.legalName} — Email: ${c.email} · Phone: ${c.phone}.`,
        `Registered/Operating Address: ${c.addressLines.join(' ')}`,
      ],
    },
  ],
});

// ──────────────────────── Refund Policy ────────────────────────
const refundPolicy = (c: CompanyInfo): LegalDoc => ({
  title: 'Refund Policy',
  intro:
    `This Refund Policy explains refunds for purchases made on ${c.product} (${c.websiteUrl}), ` +
    `operated by ${c.legalName}. All services are digital in nature.`,
  sections: [
    {
      heading: '1. Digital Product / Service Refunds',
      paragraphs: [
        'Our products are digital tools, reports, subscriptions, training content and guided advisory sessions. Because access is delivered electronically, refunds are considered only in the specific cases set out below.',
      ],
    },
    {
      heading: '2. Duplicate Payment',
      paragraphs: [
        'If you were charged more than once for the same purchase, the duplicate amount will be refunded in full after verification.',
      ],
    },
    {
      heading: '3. Failed Transaction',
      paragraphs: [
        'If your payment was debited but the transaction failed and no access or service was delivered, the amount will be refunded in full after verification with the payment gateway.',
      ],
    },
    {
      heading: '4. Non-Delivery Due to Technical Issue',
      paragraphs: [
        'If a successful payment did not result in delivery of the purchased digital service due to a technical issue on our side, you are entitled to a full refund (or, at your choice, delivery of the service).',
      ],
    },
    {
      heading: '5. Non-Refundable Cases',
      paragraphs: [
        'Once a digital service has been accessed, a report has been generated/delivered, credits have been consumed, or a coaching/advisory session has been delivered, the corresponding amount is non-refundable, except where required by applicable law.',
      ],
    },
    {
      heading: '6. Refund Processing Timeline',
      paragraphs: [
        'Approved refunds are processed within 7–10 working days after approval.',
      ],
    },
    {
      heading: '7. Original Payment Method',
      paragraphs: [
        'All approved refunds are issued to the original payment method used for the purchase.',
      ],
    },
    {
      heading: '8. How to Reach Us',
      paragraphs: [
        `For refund requests, email ${c.email} or call ${c.phone}. Please include your registered email and payment reference.`,
        `${c.legalName}, ${c.addressLines.join(' ')}`,
      ],
    },
  ],
});

// ─────────────────────── Cancellation Policy ───────────────────────
const cancellationPolicy = (c: CompanyInfo): LegalDoc => ({
  title: 'Cancellation Policy',
  intro:
    `This Cancellation Policy explains how cancellations work for purchases made on ${c.product} ` +
    `(${c.websiteUrl}), operated by ${c.legalName}.`,
  sections: [
    {
      heading: '1. Cancelling a Subscription',
      bullets: [
        'You may cancel your subscription at any time from your account settings within the app, or by emailing us.',
        'Cancellation stops all future billing — no further charges will be made after you cancel.',
        'Your plan benefits remain active until the end of the current paid billing period; the subscription is not renewed thereafter.',
      ],
    },
    {
      heading: '2. Cancelling Digital Reports / Services',
      paragraphs: [
        'One-time purchases (such as a digital report, credits or a single advisory session) can be cancelled only before the service has been delivered or the report has been generated. Once delivery has begun, the purchase cannot be cancelled.',
      ],
    },
    {
      heading: '3. When Cancellation Is Allowed',
      bullets: [
        'Subscriptions: at any time, effective from the next billing cycle.',
        'Scheduled coaching/advisory sessions: cancellation is allowed before the scheduled session start time, subject to rescheduling where applicable.',
        'Digital reports/credits: only before generation/consumption.',
      ],
    },
    {
      heading: '4. Effect on Future Billing',
      paragraphs: [
        'Cancelling a subscription stops all future recurring billing. You will not be charged again once the cancellation is confirmed.',
      ],
    },
    {
      heading: '5. Used / Delivered Digital Services',
      paragraphs: [
        'Digital services that have already been used, delivered or consumed (accessed reports, consumed credits, completed sessions) are not refundable upon cancellation. Refund eligibility is governed by our Refund Policy.',
      ],
    },
    {
      heading: '6. Contact for Cancellations',
      paragraphs: [
        `To cancel or for any cancellation query, email ${c.email} or call ${c.phone} with your registered email and payment reference.`,
        `${c.legalName}, ${c.addressLines.join(' ')}`,
      ],
    },
  ],
});

// ───────────────────────── Delivery Policy ─────────────────────────
const deliveryPolicy = (c: CompanyInfo): LegalDoc => ({
  title: 'Delivery Policy',
  intro:
    `All services provided through ${c.product} (${c.websiteUrl}) by ${c.legalName} are digital in ` +
    `nature. There is no physical shipment of goods. This policy explains how access to paid services is delivered.`,
  sections: [
    {
      heading: '1. Services Are Digital',
      paragraphs: [
        'All services provided through JELCOS.AI are digital in nature. After successful payment confirmation, access to digital tools, reports, subscriptions, training content or guided advisory sessions will be provided electronically through the website, email, user dashboard or scheduled online session, as applicable.',
      ],
    },
    {
      heading: '2. How Delivery Happens',
      bullets: [
        'Website dashboard: your active plan, credits and reports appear in your account.',
        'Email: confirmations and downloadable reports may be sent to your registered email.',
        'Downloadable report: where applicable, reports can be downloaded from your account.',
        'Online session: guided advisory/coaching sessions are delivered at the scheduled time via an online link.',
        'Account access: subscription features unlock automatically for the duration of your billing period.',
      ],
    },
    {
      heading: '3. Usual Delivery Timeline',
      paragraphs: [
        'Access to subscriptions and credits is granted instantly, and in all cases within 24 hours, of a successful payment. Scheduled sessions are delivered at the agreed session time.',
      ],
    },
    {
      heading: '4. Technical Delay',
      paragraphs: [
        'If your purchase is not reflected in your account within 24 hours of a successful payment due to a technical issue, please contact us and we will resolve it promptly or issue a refund as per our Refund Policy.',
      ],
    },
    {
      heading: '5. Support Contact',
      paragraphs: [
        `For any delivery issue, contact ${c.legalName} at ${c.email} or ${c.phone} with your registered email and payment reference.`,
      ],
    },
  ],
});

const BUILDERS: Record<string, (c: CompanyInfo) => LegalDoc> = {
  privacy: privacyPolicy,
  terms: termsOfUse,
  refund: refundPolicy,
  cancellation: cancellationPolicy,
  delivery: deliveryPolicy,
};

/** Build every legal doc from a (possibly Admin-overridden) company profile. */
export const getLegalDocs = (c: CompanyInfo = COMPANY): Record<string, LegalDoc> => ({
  privacy: privacyPolicy(c),
  terms: termsOfUse(c),
  refund: refundPolicy(c),
  cancellation: cancellationPolicy(c),
  delivery: deliveryPolicy(c),
});

/** Build a single legal doc by slug. */
export const getLegalDoc = (slug: string, c: CompanyInfo = COMPANY): LegalDoc =>
  (BUILDERS[slug] || privacyPolicy)(c);

// Static fallbacks (built from defaults) for any non-reactive consumer.
export const PRIVACY_POLICY = privacyPolicy(COMPANY);
export const TERMS_OF_USE = termsOfUse(COMPANY);
export const REFUND_POLICY = refundPolicy(COMPANY);
export const CANCELLATION_POLICY = cancellationPolicy(COMPANY);
export const DELIVERY_POLICY = deliveryPolicy(COMPANY);
export const LEGAL_DOCS: Record<string, LegalDoc> = getLegalDocs(COMPANY);
