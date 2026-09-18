import { showAlert } from './alert';

export function isCTTAccessAllowed(user: any, acmAccess?: any): boolean {
  if (!user && !acmAccess) return false;

  // 1. Admin roles override (Always allowed)
  const role = (user?.role || '').toLowerCase();
  if (['super_admin', 'admin', 'co_admin'].includes(role) || user?.is_admin) {
    return true;
  }

  const utype = (user?.user_type || acmAccess?.user_type || acmAccess?.userType || '').toLowerCase().trim();
  const plan = (user?.subscription_plan || acmAccess?.subscription_plan || acmAccess?.subscriptionPlan || '').toLowerCase().trim();

  // 2. Tester tiers or paid user_type override
  if (['alpha', 'beta', 'unit_tester', 'integration_tester', 'paid', 'admin', 'super_admin', 'co_admin'].includes(utype)) {
    return true;
  }

  // 3. Explicit On-Demand check (Restricted / Blocked)
  if (utype.startsWith('on_demand') || plan.startsWith('on_demand')) {
    return false;
  }

  // 4. Active Subscription plan check (Basic, Pro, Premium, Enterprise, Starter, Paid)
  if (plan && !['none', 'free', ''].includes(plan)) {
    return true;
  }

  // 5. Free plan check (Restricted / Blocked)
  if (['free', 'guest', 'trial', ''].includes(utype) && ['', 'none', 'free'].includes(plan)) {
    return false;
  }

  return false;
}

export function promptCTTUpgrade(router: any, customMsg?: string) {
  showAlert(
    'Subscription Required',
    customMsg || 'Task Tracker (CTT) is available exclusively for Subscription Plan members (Basic, Pro, Premium). Free and On-Demand plans cannot access or create tasks in CTT.',
    [
      { text: 'Upgrade Plan', onPress: () => router.push('/subscription-plans') },
      { text: 'Cancel', style: 'cancel' }
    ]
  );
}

export function isLifestyleAccessAllowed(user: any, acmAccess?: any): boolean {
  // Same plan access policy: Free and On-Demand plans restricted, Subscription plans allowed
  return isCTTAccessAllowed(user, acmAccess);
}

export function promptLifestyleUpgrade(router: any, customMsg?: string) {
  showAlert(
    'Subscription Required',
    customMsg || 'Lifestyle Dezider is available exclusively for Subscription Plan members (Basic, Pro, Premium). Free and On-Demand plans cannot access or create routines in Lifestyle Dezider.',
    [
      { text: 'Upgrade Plan', onPress: () => router.push('/subscription-plans') },
      { text: 'Cancel', style: 'cancel' }
    ]
  );
}

export function isValuesAccessAllowed(user: any, acmAccess?: any): boolean {
  // Same plan access policy: Free and On-Demand plans restricted, Subscription plans allowed
  return isCTTAccessAllowed(user, acmAccess);
}

export function promptValuesUpgrade(router: any, customMsg?: string) {
  showAlert(
    'Subscription Required',
    customMsg || 'Values Tracker is available exclusively for Subscription Plan members (Basic, Pro, Premium). Free and On-Demand plans cannot access or view Values Tracker.',
    [
      { text: 'Upgrade Plan', onPress: () => router.push('/subscription-plans') },
      { text: 'Cancel', style: 'cancel' }
    ]
  );
}

export function isATEXAccessAllowed(user: any, acmAccess?: any): boolean {
  if (!user && !acmAccess) return false;

  // 1. Admin roles override (Always allowed)
  const role = (user?.role || '').toLowerCase();
  if (['super_admin', 'admin', 'co_admin'].includes(role) || user?.is_admin) {
    return true;
  }

  const utype = (user?.user_type || acmAccess?.user_type || acmAccess?.userType || '').toLowerCase().trim();
  const plan = (user?.subscription_plan || acmAccess?.subscription_plan || acmAccess?.subscriptionPlan || '').toLowerCase().trim();

  // 2. Tester tiers override
  if (['alpha', 'beta', 'unit_tester', 'integration_tester', 'admin', 'super_admin', 'co_admin'].includes(utype)) {
    return true;
  }

  // 3. Explicit On-Demand check (Restricted / Blocked)
  if (utype.startsWith('on_demand') || plan.startsWith('on_demand')) {
    return false;
  }

  // 4. Basic plan check (Restricted / Blocked for ATEX per user request)
  if (utype === 'basic' || plan === 'basic' || plan.startsWith('basic')) {
    return false;
  }

  // 5. Free plan check (Restricted / Blocked)
  if (['free', 'guest', 'trial', ''].includes(utype) && ['', 'none', 'free'].includes(plan)) {
    return false;
  }

  // 6. Pro, Premium, Enterprise, Starter, Paid subscription plan check (Allowed)
  if (plan && !['none', 'free', 'basic', ''].includes(plan)) {
    return true;
  }

  if (utype === 'paid' && plan !== 'basic') {
    return true;
  }

  return false;
}

export function promptATEXUpgrade(router: any, customMsg?: string) {
  showAlert(
    'Subscription Required',
    customMsg || 'ATEX Effort Estimation is available exclusively for Pro, Premium, and Enterprise plan members. Free, On-Demand, and Basic plan users cannot access ATEX.',
    [
      { text: 'Upgrade Plan', onPress: () => router.push('/subscription-plans') },
      { text: 'Cancel', style: 'cancel' }
    ]
  );
}

export function isOrgsAccessAllowed(user: any, acmAccess?: any): boolean {
  if (!user && !acmAccess) return false;

  // 1. Admin roles override (Always allowed)
  const role = (user?.role || '').toLowerCase();
  if (['super_admin', 'admin', 'co_admin'].includes(role) || user?.is_admin) {
    return true;
  }

  const utype = (user?.user_type || acmAccess?.user_type || acmAccess?.userType || '').toLowerCase().trim();
  const plan = (user?.subscription_plan || acmAccess?.subscription_plan || acmAccess?.subscriptionPlan || '').toLowerCase().trim();

  // 2. Tester tiers override
  if (['alpha', 'beta', 'unit_tester', 'integration_tester', 'admin', 'super_admin', 'co_admin'].includes(utype)) {
    return true;
  }

  // 3. Explicit On-Demand check (Restricted / Blocked)
  if (utype.startsWith('on_demand') || plan.startsWith('on_demand')) {
    return false;
  }

  // 4. Basic and Pro plan check (Restricted / Blocked per user request: "free, on demand, basi, pro also")
  if (['basic', 'pro'].includes(utype) || ['basic', 'pro'].includes(plan) || plan.startsWith('basic') || plan.startsWith('pro')) {
    return false;
  }

  // 5. Free plan check (Restricted / Blocked)
  if (['free', 'guest', 'trial', ''].includes(utype) && ['', 'none', 'free'].includes(plan)) {
    return false;
  }

  // 6. Premium & Enterprise plan check (Allowed)
  if (plan && ['premium', 'enterprise'].includes(plan)) {
    return true;
  }

  if (utype === 'paid' && ['premium', 'enterprise'].includes(plan)) {
    return true;
  }

  return false;
}

export function promptOrgsUpgrade(router: any, customMsg?: string) {
  showAlert(
    'Subscription Required',
    customMsg || 'My Organizations (7x7 Matrix & 6 LeGs Goal Tree) is available exclusively for Premium and Enterprise plan members. Free, On-Demand, Basic, and Pro plan users cannot access Orgs.',
    [
      { text: 'Upgrade Plan', onPress: () => router.push('/subscription-plans') },
      { text: 'Cancel', style: 'cancel' }
    ]
  );
}

export function isManifestationAccessAllowed(user: any, acmAccess?: any): boolean {
  return isOrgsAccessAllowed(user, acmAccess);
}

export function promptManifestationUpgrade(router: any, customMsg?: string) {
  showAlert(
    'Subscription Required',
    customMsg || 'Goal Manifestation (CAB-FAME) is available exclusively for Premium and Enterprise plan members. Free, On-Demand, Basic, and Pro plan users cannot access Goal Manifestation.',
    [
      { text: 'Upgrade Plan', onPress: () => router.push('/subscription-plans') },
      { text: 'Cancel', style: 'cancel' }
    ]
  );
}

export function isAIMAccessAllowed(user: any, acmAccess?: any): boolean {
  return isCTTAccessAllowed(user, acmAccess);
}

export function promptAIMUpgrade(router: any, customMsg?: string) {
  showAlert(
    'Subscription Required',
    customMsg || 'AIM Manager (Addictions & Irritations) is available exclusively for Subscription Plan members (Basic, Pro, Premium). Free and On-Demand plans cannot access AIM Manager.',
    [
      { text: 'Upgrade Plan', onPress: () => router.push('/subscription-plans') },
      { text: 'Cancel', style: 'cancel' }
    ]
  );
}

export function isTEPFIAccessAllowed(user: any, acmAccess?: any): boolean {
  return isATEXAccessAllowed(user, acmAccess);
}

export function promptTEPFIUpgrade(router: any, customMsg?: string) {
  showAlert(
    'Subscription Required',
    customMsg || 'TEPFI (Capabilities & Resources Index) is available exclusively for Pro, Premium, and Enterprise plan members. Free, On-Demand, and Basic plan users cannot access TEPFI.',
    [
      { text: 'Upgrade Plan', onPress: () => router.push('/subscription-plans') },
      { text: 'Cancel', style: 'cancel' }
    ]
  );
}

export function isConsciousnessAccessAllowed(user: any, acmAccess?: any): boolean {
  return isOrgsAccessAllowed(user, acmAccess);
}

export function promptConsciousnessUpgrade(router: any, customMsg?: string) {
  showAlert(
    'Subscription Required',
    customMsg || 'Consciousness Diary is available exclusively for Premium and Enterprise plan members. Free, On-Demand, Basic, and Pro plan users cannot access Consciousness Diary.',
    [
      { text: 'Upgrade Plan', onPress: () => router.push('/subscription-plans') },
      { text: 'Cancel', style: 'cancel' }
    ]
  );
}

export function isJournalAccessAllowed(user: any, acmAccess?: any): boolean {
  return isCTTAccessAllowed(user, acmAccess);
}

export function promptJournalUpgrade(router: any, customMsg?: string) {
  showAlert(
    'Subscription Required',
    customMsg || 'Learning Journal is available exclusively for Subscription Plan members (Basic, Pro, Premium). Free and On-Demand plans cannot access Learning Journal.',
    [
      { text: 'Upgrade Plan', onPress: () => router.push('/subscription-plans') },
      { text: 'Cancel', style: 'cancel' }
    ]
  );
}

export function isDecisionTemplatesAccessAllowed(user: any, acmAccess?: any): boolean {
  return isCTTAccessAllowed(user, acmAccess);
}

export function promptDecisionTemplatesUpgrade(router: any, customMsg?: string) {
  showAlert(
    'Subscription Required',
    customMsg || 'Decision Templates (The Decider Store) are available exclusively for Subscription Plan members (Basic, Pro, Premium). Free and On-Demand plans cannot access Decision Templates.',
    [
      { text: 'Upgrade Plan', onPress: () => router.push('/subscription-plans') },
      { text: 'Cancel', style: 'cancel' }
    ]
  );
}

export function isDeciderAppsAccessAllowed(user: any, acmAccess?: any): boolean {
  return isATEXAccessAllowed(user, acmAccess);
}

export function promptDeciderAppsUpgrade(router: any, customMsg?: string) {
  showAlert(
    'Subscription Required',
    customMsg || 'Decider Apps @ Best Option Finders are available exclusively for Pro, Premium, and Enterprise plan members. Free, On-Demand, and Basic plan users cannot access Decider Apps.',
    [
      { text: 'Upgrade Plan', onPress: () => router.push('/subscription-plans') },
      { text: 'Cancel', style: 'cancel' }
    ]
  );
}

export function isFindTemplatesAccessAllowed(user: any, acmAccess?: any): boolean {
  return isATEXAccessAllowed(user, acmAccess);
}

export function promptFindTemplatesUpgrade(router: any, customMsg?: string) {
  showAlert(
    'Subscription Required',
    customMsg || 'Find Templates is available exclusively for Pro, Premium, and Enterprise plan members. Free, On-Demand, and Basic plan users cannot access Find Templates.',
    [
      { text: 'Upgrade Plan', onPress: () => router.push('/subscription-plans') },
      { text: 'Cancel', style: 'cancel' }
    ]
  );
}

export function promptMPPSUpgrade(router: any, customMsg?: string) {
  showAlert(
    'Subscription Required',
    customMsg || 'MPPS Analysis is available exclusively for Subscription Plan members (Basic, Pro, Premium). Free and On-Demand plans cannot access MPPS Analysis.',
    [
      { text: 'Upgrade Plan', onPress: () => router.push('/subscription-plans') },
      { text: 'Cancel', style: 'cancel' }
    ]
  );
}

export function promptXLSUpgrade(router: any, customMsg?: string) {
  showAlert(
    'Subscription Required',
    customMsg || 'Export and Import XLS are available exclusively for Subscription Plan members (Basic, Pro, Premium). Free and On-Demand plans cannot access XLS import/export.',
    [
      { text: 'Upgrade Plan', onPress: () => router.push('/subscription-plans') },
      { text: 'Cancel', style: 'cancel' }
    ]
  );
}

export function promptGsheetUpgrade(router: any, customMsg?: string) {
  showAlert(
    'Subscription Required',
    customMsg || 'Google Sheet, Import Sheet, and Import from URL features are available exclusively for Pro, Premium, and Enterprise plan members. Free, On-Demand, and Basic plan users cannot access these import options.',
    [
      { text: 'Upgrade Plan', onPress: () => router.push('/subscription-plans') },
      { text: 'Cancel', style: 'cancel' }
    ]
  );
}

export function promptAIPrioritizeUpgrade(router: any, customMsg?: string) {
  showAlert(
    'Subscription Required',
    customMsg || 'Prioritize with AI is available exclusively for Pro, Premium, and Enterprise plan members. Free, On-Demand, and Basic plan users cannot access AI Prioritization.',
    [
      { text: 'Upgrade Plan', onPress: () => router.push('/subscription-plans') },
      { text: 'Cancel', style: 'cancel' }
    ]
  );
}









