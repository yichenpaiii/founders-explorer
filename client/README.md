# React + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Babel](https://babeljs.io/) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.

---

## Cloudflare Pages Functions + Supabase (Scheme A)

We proxy all `/api` requests to a Cloudflare Pages Functions endpoint that talks to Supabase PostgREST.

Local dev (two terminals):

1) Front-end with HMR

```bash
cd client
npm install
npm run dev
```

2) Pages Functions (Supabase proxy)

```bash
# from repo root
wrangler pages dev ./client
```

`vite.config.js` proxies `/api` to `http://127.0.0.1:8788`.

Environment variables for the Functions are read from Cloudflare in production, and from `.dev.vars` in local dev.

Create `client/.dev.vars` (not committed) based on the example:

```
SUPABASE_URL=your-supabase-url
SUPABASE_ANON_KEY=your-anon-key
```

Then run `wrangler pages dev ./client`.

### Production

Deploy the `client` directory as a Cloudflare Pages project.

- Set `SUPABASE_URL` and `SUPABASE_ANON_KEY` as project environment variables in Cloudflare.
- Pages Functions will serve your API at `/api/*` on the same origin.

### Supabase view expected

The Functions call a Supabase PostgREST view named `courses_search_view` and expect these columns:

- `id, course_name, course_code, url, credits, lang, semester, exam_form, workload`
- `prof_name, type, prof_names, offering_types`
- `max_score_skills_sigmoid, max_score_product_sigmoid, max_score_venture_sigmoid, max_score_foundations_sigmoid`

Filters supported by query params mirror the UI controls: `q, type, semester, creditsMin, creditsMax, available_programs, minSkills, minProduct, minVenture, minFoundations` and pagination `page, pageSize`. Sorting supports `course_name, credits, workload, score_*`.
