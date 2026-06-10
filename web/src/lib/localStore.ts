const OVERVIEW_SEEN_PREFIX = "mxa:overview-seen:";
const SCROLL_HINT_KEY = "mxa:scroll-hint-shown";
const OVERVIEW_SEEN_TTL_MS = 24 * 60 * 60 * 1000;

function getStorage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function markOverviewSeen(projectId: string, now = Date.now()): void {
  const storage = getStorage();
  if (!storage) {
    return;
  }
  try {
    storage.setItem(`${OVERVIEW_SEEN_PREFIX}${projectId}`, String(now));
  } catch {
    // localStorage can fail in private mode; the app should keep working.
  }
}

export function hasSeenOverview(projectId: string, now = Date.now()): boolean {
  const storage = getStorage();
  if (!storage) {
    return false;
  }
  const raw = storage.getItem(`${OVERVIEW_SEEN_PREFIX}${projectId}`);
  const timestamp = raw ? Number(raw) : Number.NaN;
  return Number.isFinite(timestamp) && now - timestamp <= OVERVIEW_SEEN_TTL_MS;
}

export function cleanupExpiredOverviewSeen(now = Date.now()): void {
  const storage = getStorage();
  if (!storage) {
    return;
  }
  try {
    for (let index = storage.length - 1; index >= 0; index -= 1) {
      const key = storage.key(index);
      if (!key?.startsWith(OVERVIEW_SEEN_PREFIX)) {
        continue;
      }
      const timestamp = Number(storage.getItem(key));
      if (!Number.isFinite(timestamp) || now - timestamp > OVERVIEW_SEEN_TTL_MS) {
        storage.removeItem(key);
      }
    }
  } catch {
    // Cleanup is best-effort only.
  }
}

export function shouldShowScrollHint(): boolean {
  const storage = getStorage();
  if (!storage) {
    return false;
  }
  return storage.getItem(SCROLL_HINT_KEY) !== "1";
}

export function markScrollHintShown(): void {
  const storage = getStorage();
  if (!storage) {
    return;
  }
  try {
    storage.setItem(SCROLL_HINT_KEY, "1");
  } catch {
    // Non-critical hint state.
  }
}
