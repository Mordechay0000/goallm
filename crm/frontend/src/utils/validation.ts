/**
 * Shared validation utilities for the CRM
 */

/** Normalize phone: extract digits only */
export function normalizePhone(s: string): string {
  return (s || '').replace(/\D/g, '');
}

/**
 * Validate phone.
 * - Israeli (without +): must start with 05 and be exactly 10 digits.
 * - International (with +): must start with + and contain 8–15 digits in total (after removing separators).
 * Returns error message or empty string if valid.
 */
export function validatePhone(phone: string): string {
  const raw = (phone || '').trim();
  const digits = normalizePhone(raw);
  // ריק – יטופל על ידי שדות חובה במקום אחר
  if (!raw) return '';
  if (digits.length === 0) return 'מספר טלפון לא תקין';

  // מספר בינלאומי
  if (raw.startsWith('+')) {
    // מאפשר בין 8 ל־15 ספרות (סטייל E.164, אבל גמיש עם רווחים/מקפים)
    if (digits.length < 8 || digits.length > 15) {
      return 'מספר בינלאומי לא תקין – יש להזין בין 8 ל־15 ספרות אחרי הקידומת';
    }
    return '';
  }

  // מספר ישראלי: חייב להתחיל ב־05 ולהיות 10 ספרות בדיוק
  if (!digits.startsWith('05')) {
    return 'מספר ישראלי חייב להתחיל ב־05';
  }
  if (digits.length !== 10) {
    return 'מספר ישראלי חייב להכיל 10 ספרות בדיוק';
  }

  return '';
}

/**
 * Validate domain/URL for rules and requests.
 * Accepts: example.com, *.example.com, example.com/path, localhost, IP addresses.
 * Returns error message or empty string if valid.
 */
export function validateDomainOrUrl(input: string): string {
  if (!input || !input.trim()) return 'שדה חובה';

  let clean = input.trim();
  if (clean.startsWith('http://')) clean = clean.substring(7);
  else if (clean.startsWith('https://')) clean = clean.substring(8);

  if (clean.includes('://')) return 'כתובת לא תקינה - הסר את הפרוטוקול';
  if (/\/{3,}/.test(clean)) return 'כתובת לא תקינה - יותר מדי לוכסנים';
  if (/[<>"|\\]/.test(clean)) return 'כתובת לא תקינה - תווים לא חוקיים';

  for (let i = 0; i < clean.length; i++) {
    if (clean.charCodeAt(i) <= 0x1f) return 'כתובת לא תקינה - תווים לא חוקיים';
  }

  if (clean.startsWith('*.')) clean = clean.substring(2);

  if (!clean.length) return 'כתובת לא תקינה - שדה ריק';

  const parts = clean.split('/');
  const domain = parts[0];

  if (!domain.length) return 'כתובת לא תקינה - אין דומיין';

  // localhost
  if (domain === 'localhost') return '';

  // IP address
  if (/^(\d{1,3}\.){3}\d{1,3}$/.test(domain)) {
    const octets = domain.split('.').map(Number);
    if (octets.every((n) => n >= 0 && n <= 255)) return '';
    return 'כתובת לא תקינה - כתובת IP לא תקינה';
  }

  // Domain: must have at least one dot (e.g. example.com) or be a valid hostname
  const hostnameRe = /^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*$/;
  if (!domain.includes('.')) {
    return 'כתובת לא תקינה - דומיין חייב לכלול נקודה (למשל example.com)';
  }
  if (!hostnameRe.test(domain)) {
    return 'כתובת לא תקינה - דומיין לא תקין';
  }

  return '';
}

/** Normalize URL for display/storage - strip protocol */
export function normalizeUrlForInput(url: string): string {
  if (!url || !url.trim()) return '';
  return url.trim().replace(/^https?:\/\//, '');
}

/**
 * Normalize URL for rules: strip protocol and strip www. from domain.
 * Returns normalized URL and whether the original had www. (so UI can show a message).
 */
export function normalizeUrlForRule(input: string): { normalized: string; hadWww: boolean } {
  if (!input || !input.trim()) return { normalized: '', hadWww: false };
  let v = input.trim();
  if (v.startsWith('https://')) v = v.substring(8);
  else if (v.startsWith('http://')) v = v.substring(7);
  let hadWww = false;
  let prefix = '';
  if (v.startsWith('*.')) {
    prefix = '*.';
    v = v.substring(2);
  }
  const slashIdx = v.indexOf('/');
  const domainPart = slashIdx >= 0 ? v.substring(0, slashIdx) : v;
  const rest = slashIdx >= 0 ? v.substring(slashIdx) : '';
  const domain = domainPart.toLowerCase();
  let normalizedDomain = domain;
  if (domain.startsWith('www.')) {
    normalizedDomain = domain.substring(4);
    hadWww = true;
  }
  const normalized = prefix + normalizedDomain + rest;
  return { normalized, hadWww };
}

/** Message to show when user entered www. and we normalized it */
export const WWW_NORMALIZED_MESSAGE = 'ההתייחסות ל-www. היא כמו בלי www – הכלל נשמר ללא www.';

/**
 * Process URL input on type/paste: strip protocol (http/https), strip *. prefix, strip www. from domain.
 * When *. is found, returns setSubdomains: true. When www. was stripped, returns hadWww: true.
 */
export function processUrlInput(value: string): { cleaned: string; setSubdomains?: boolean; hadWww?: boolean } {
  let v = value;
  let setSubdomains: boolean | undefined;
  let hadWww = false;

  if (v.startsWith('https://')) v = v.substring(8);
  else if (v.startsWith('http://')) v = v.substring(7);

  if (v.startsWith('*.')) {
    v = v.substring(2);
    setSubdomains = true;
  }

  const slashIdx = v.indexOf('/');
  const domainPart = slashIdx >= 0 ? v.substring(0, slashIdx) : v;
  const rest = slashIdx >= 0 ? v.substring(slashIdx) : '';
  if (domainPart.toLowerCase().startsWith('www.')) {
    v = domainPart.substring(4).toLowerCase() + rest;
    hadWww = true;
  }

  return { cleaned: v, setSubdomains, hadWww };
}
