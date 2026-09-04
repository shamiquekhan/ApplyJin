/** Single source of the API base — resolves lazily so VITE_API_URL
 * always applies, and every module can import it cheaply. */

export const API_BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");
