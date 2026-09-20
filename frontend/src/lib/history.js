// Session history of analyses, persisted to localStorage so it survives reloads.
const KEY = 'satyascore_history_v1'
const MAX = 30

export function loadHistory() {
  try {
    const raw = localStorage.getItem(KEY)
    const items = raw ? JSON.parse(raw) : []
    return Array.isArray(items) ? items : []
  } catch {
    return []
  }
}

export function saveHistory(items) {
  try {
    localStorage.setItem(KEY, JSON.stringify(items.slice(0, MAX)))
  } catch {
    // storage full / disabled — history just won't persist; not fatal
  }
}
