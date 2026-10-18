/**
 * The document-boundary recovery for a route chunk that never arrived.
 *
 * A second `import()` of the same URL is not a recovery: once Chromium has
 * recorded a failed module fetch, the repeat can be answered from that record
 * without touching the network. Reloading re-requests the whole page's modules,
 * keeps the hash route, and keeps this browser's workspace session. The failed
 * route page never mounted, so there is no draft on it to lose.
 */
export function reloadPage(): void {
  window.location.reload();
}
