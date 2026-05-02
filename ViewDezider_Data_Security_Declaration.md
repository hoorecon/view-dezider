# DATA SECURITY DECLARATION

**Organization:** VEALES (View Dezider Platform)  
**Date:** 02 May 2026  
**Document Version:** 1.0  
**Classification:** Confidential  

---

## 1. PURPOSE

This declaration outlines the data security practices, encryption standards, user consent mechanisms, and data handling policies implemented by VEALES ("the Company") for the View Dezider platform in relation to the integration with DigiLocker / API Setu services for identity verification (eKYC) of platform participants.

---

## 2. DATA COLLECTED VIA DIGILOCKER

The following data points are fetched **only after explicit user consent** via the DigiLocker OAuth2 authorization flow:

| Data Point | Source Document | Purpose |
|-----------|----------------|---------|
| Full Name | Aadhaar | Verify participant identity in group decisions |
| Date of Birth | Aadhaar | Age verification for compliance |
| Gender | Aadhaar | Optional demographic for SME profiling |
| Photo | Aadhaar | Visual identity confirmation by session admin |
| Udyam/CIN Number | Udyam Certificate | Verify business entity legitimacy |

**No Aadhaar number is stored.** Only the verified name, DOB, and verification status are retained.

---

## 3. ENCRYPTION STANDARDS

| Layer | Standard | Implementation |
|-------|----------|---------------|
| Data in Transit | TLS 1.3 | All API calls between View Dezider servers and DigiLocker/API Setu endpoints are encrypted via HTTPS with TLS 1.3 |
| Data at Rest | AES-256 | All KYC verification records stored in MongoDB are encrypted at rest using AES-256 encryption |
| Token Storage | HMAC-SHA256 | OAuth2 access tokens and refresh tokens are hashed before storage; plaintext tokens are never persisted |
| Password Hashing | bcrypt (cost factor 12) | User account passwords are hashed using bcrypt and never stored in plaintext |
| API Authentication | JWT (RS256) | All internal API calls are authenticated via signed JSON Web Tokens |

---

## 4. USER CONSENT FLOW

The following multi-step consent mechanism is enforced **before** any DigiLocker data is accessed:

1. **Informed Consent Screen** — User is shown a clear explanation of what data will be fetched, why it is needed, and how it will be used, before initiating the DigiLocker flow.
2. **DigiLocker OAuth Authorization** — User is redirected to the official DigiLocker portal where they independently authenticate and grant consent to share specific documents.
3. **Granular Document Selection** — User selects which documents to share (Aadhaar, Udyam, etc.) within the DigiLocker interface. No documents are fetched without user selection.
4. **Post-Verification Confirmation** — After verification, user is shown exactly what data was retrieved and given the option to revoke access at any time.
5. **Revocation Right** — Users can request complete deletion of their KYC data from View Dezider at any time via the app settings or by contacting support@veales.com.

---

## 5. NO THIRD-PARTY DATA SHARING

We hereby declare that:

- **NO** personally identifiable information (PII) obtained via DigiLocker is shared with any third party, partner, advertiser, analytics provider, or external service.
- **NO** Aadhaar number, biometric data, or raw document images are stored on our servers.
- **NO** KYC data is used for any purpose other than participant identity verification within the View Dezider decision-making platform.
- **NO** data is transferred outside the territory of India. All servers and databases are hosted within India.
- **NO** automated profiling, scoring, or AI training is performed on KYC data.

---

## 6. DATA RETENTION & DELETION

| Scenario | Retention Period | Action |
|----------|-----------------|--------|
| Active verified user | Duration of active account | Data retained for verification status |
| User requests deletion | Within 48 hours | All KYC records permanently deleted |
| Account inactive > 12 months | Auto-purge | KYC data auto-deleted after 12 months of inactivity |
| DigiLocker OAuth tokens | 24 hours max | Tokens auto-expire and are purged from storage |

---

## 7. INCIDENT RESPONSE

In the event of any data breach or security incident involving DigiLocker-sourced data:

- CERT-In will be notified within **6 hours** as per Indian IT Act requirements.
- Affected users will be notified within **24 hours** with details of the breach and remediation steps.
- DigiLocker/API Setu team will be informed immediately for coordinated response.

---

## 8. COMPLIANCE

This implementation complies with:

- **Information Technology Act, 2000** (India)
- **IT (Reasonable Security Practices and Procedures) Rules, 2011**
- **UIDAI Aadhaar Data Vault Guidelines**
- **Digital Personal Data Protection Act (DPDPA), 2023**
- **API Setu Terms of Use and Privacy Statement**

---

## 9. AUTHORIZED SIGNATORY

**Name:** A D Shezhiyan Raj  
**Designation:** Founder & CEO  
**Organization:** VEALES  
**Platform:** View Dezider  
**Email:** [Your Email]  
**Contact:** [Your Phone]  

**Signature:** ____________________________  

**Date:** 02 May 2026  

---

*This document is issued by VEALES in support of the DigiLocker / API Setu partner registration application. The declarations made herein are accurate and binding.*
