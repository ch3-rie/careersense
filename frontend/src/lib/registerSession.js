const KEY = "cs_register_complete";
let memoryFlag = false;

export function markJustRegistered() {
  memoryFlag = true;
  try {
    sessionStorage.setItem(KEY, "1");
  } catch {
    /* ignore quota / private mode */
  }
}

export function clearJustRegistered() {
  memoryFlag = false;
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}

export function justRegistered() {
  if (memoryFlag) return true;
  try {
    return sessionStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}
