/**
 * Industrial Formatting & Presentation Utilities
 * 
 * Strict rule: undefined != zero.
 * If value is missing, return "Waiting for data".
 */

export function formatValue(value: number | undefined | null, decimals = 2, fallback = 'Waiting for data'): string {
  if (value === undefined || value === null || isNaN(value)) {
    return fallback;
  }
  return value.toFixed(decimals);
}

export function formatValueWithUnit(value: number | undefined | null, unit: string, decimals = 2): string {
  if (value === undefined || value === null || isNaN(value)) {
    return 'Waiting for data';
  }
  return `${value.toFixed(decimals)} ${unit}`;
}

export function formatTimestamp(isoString: string | number | undefined | null): string {
  if (!isoString) return 'Waiting for data';
  try {
    const d = typeof isoString === 'number' ? new Date(isoString) : new Date(isoString);
    if (isNaN(d.getTime())) return 'Invalid date';
    return d.toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
  } catch {
    return 'Waiting for data';
  }
}

export function formatRelativeTime(isoString: string | undefined | null): string {
  if (!isoString) return 'Waiting for data';
  try {
    const d = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffSec = Math.floor(diffMs / 1000);
    if (diffSec < 2) return 'just now';
    if (diffSec < 60) return `${diffSec}s ago`;
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHours = Math.floor(diffMin / 60);
    return `${diffHours}h ago`;
  } catch {
    return 'Waiting for data';
  }
}

export function truncateHash(hash: string | undefined | null, leadingChars = 6, trailingChars = 4): string {
  if (!hash) return 'Not available';
  if (hash.length <= leadingChars + trailingChars) return hash;
  return `${hash.slice(0, leadingChars)}...${hash.slice(-trailingChars)}`;
}
