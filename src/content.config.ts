import { defineCollection } from 'astro:content';
import { z } from 'astro/zod';
import { glob } from 'astro/loaders';

const books = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/books' }),
  schema: z.object({
    title: z.string(),
    author: z.string(),
    originalTitle: z.string().optional().default(''),
    year: z.number().optional(),
    publisher: z.string().optional(),
    isbn: z.string().optional(),
    language: z.string().default('ru'),
    pages: z.number().optional(),
    cover: z.string().default('/covers/default-book.svg'),
    genres: z.array(z.string()).default([]),
    status: z.enum(['read', 'reading', 'to-read', 'planned', 'neutral']).default('read'),
    loan: z.string().optional(), // e.g. "Анна" -> badge "У Анны"
    room: z.string().optional(), // e.g. "Гостиная", "Кабинет", "Спальня"
    shelf: z.string().optional(), // e.g. "полка 1", "полка 2"
    rating: z.number().min(1).max(5).optional(),
    addedAt: z.coerce.date().default(() => new Date()),
  }),
});

export const collections = { books };
