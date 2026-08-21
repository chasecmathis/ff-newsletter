import { defineCollection, z } from "astro:content";
import { glob } from "astro/loaders";

/**
 * Newsletters are prose only — the standings, scores and stat panels are
 * rendered from data/ instead. Drafts are excluded from the build, so nothing
 * ships until it has been read by a human and marked published.
 */
const newsletters = defineCollection({
  loader: glob({ pattern: "**/*.md", base: "./content/newsletters" }),
  schema: z.object({
    title: z.string(),
    week: z.number(),
    year: z.number(),
    date: z.coerce.date(),
    status: z.enum(["draft", "published"]).default("draft"),
    model: z.string().optional(),
    factIds: z.array(z.string()).default([]),
  }),
});

export const collections = { newsletters };
