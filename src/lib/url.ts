/**
 * The site is served from a GitHub Pages sub-path, so every internal link needs
 * the base prefix. Routing through here keeps that prefix in astro.config.mjs
 * only, which is what makes moving to a custom domain a one-line change.
 */
const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

export function url(path: string): string {
  const clean = path.startsWith("/") ? path : `/${path}`;
  const withSlash = clean.endsWith("/") || clean.includes(".") ? clean : `${clean}/`;
  return `${BASE}${withSlash}`;
}

export const weekUrl = (year: number, week: number) => url(`/newsletters/${year}/week_${week}/`);
export const teamUrl = (year: number, teamId: number) => url(`/teams/${year}/${teamId}/`);
