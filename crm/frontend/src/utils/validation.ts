/**
 * Shared validation utilities for the CRM
 */

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
 * Process URL input on type/paste: strip protocol (http/https), strip *. prefix.
 * When *. is found, returns setSubdomains: true so caller can check the subdomains checkbox.
 */
export function processUrlInput(value: string): { cleaned: string; setSubdomains?: boolean } {
  let v = value;
  let setSubdomains: boolean | undefined;

  if (v.startsWith('https://')) v = v.substring(8);
  else if (v.startsWith('http://')) v = v.substring(7);

  if (v.startsWith('*.')) {
    v = v.substring(2);
    setSubdomains = true;
  }

  return { cleaned: v, setSubdomains };
}
