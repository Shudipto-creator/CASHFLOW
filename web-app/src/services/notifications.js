/** Temporary UI feedback; replace with app-level toast service if needed. */
export function showNotice(setNotice, message) {
  setNotice(message)
  window.setTimeout(() => setNotice(''), 2600)
}
