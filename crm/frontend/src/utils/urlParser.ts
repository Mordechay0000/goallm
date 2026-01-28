/**
 * URL parsing utilities
 */
export function parseUrl(url: string): { domain: string; path: string | null; includeSubdomains: boolean } {
  // Remove protocol
  let cleanUrl = url.trim();
  if (cleanUrl.startsWith('http://')) {
    cleanUrl = cleanUrl.substring(7);
  } else if (cleanUrl.startsWith('https://')) {
    cleanUrl = cleanUrl.substring(8);
  }

  // Check for subdomain wildcard
  let includeSubdomains = false;
  if (cleanUrl.startsWith('*.')) {
    includeSubdomains = true;
    cleanUrl = cleanUrl.substring(2);
  }

  // Split domain and path
  const slashIndex = cleanUrl.indexOf('/');
  if (slashIndex >= 0) {
    const domain = cleanUrl.substring(0, slashIndex).toLowerCase().replace(/\.$/, '');
    const path = '/' + cleanUrl.substring(slashIndex + 1);
    return { domain, path, includeSubdomains };
  } else {
    const domain = cleanUrl.toLowerCase().replace(/\.$/, '');
    return { domain, path: null, includeSubdomains };
  }
}

export function formatUrl(domain: string, path: string | null, includeSubdomains: boolean): string {
  let url = domain;
  if (includeSubdomains && !domain.startsWith('*.')) {
    url = `*.${domain}`;
  }
  if (path) {
    url += path;
  }
  return url;
}

export function formatRuleDisplay(rule: { domain_pattern: string; path_pattern: string | null; include_subdomains: boolean }): string {
  let display = rule.domain_pattern;
  if (rule.include_subdomains && !display.startsWith('*.')) {
    display = `*.${display}`;
  }
  if (rule.path_pattern) {
    display += rule.path_pattern;
  }
  return display;
}
