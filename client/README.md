# React + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Babel](https://babeljs.io/) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.

---

## Supabase Direct Fetch

The React app talks to Supabase PostgREST directly from the browser.

### Local development

```bash
cd client
npm install
npm run dev
```

Create `client/.dev.vars` (not committed) based on the example:

```
SUPABASE_URL=your-supabase-url
SUPABASE_ANON_KEY=your-anon-key
```

When the Vite dev server starts it prints the initial Supabase response to the terminal so you can verify connectivity.

### Production

Set `SUPABASE_URL` and `SUPABASE_ANON_KEY` as environment variables in whatever platform serves the built assets. The Vite build injects them for the client bundle at compile time.

### Supabase view expected

The client reads from the Supabase PostgREST view `courses_search_view` and expects these columns:

- `id, course_name, course_code, url, credits, lang, semester, exam_form, workload`
- `prof_name, type, prof_names, offering_types`
- `max_score_skills_sigmoid, max_score_product_sigmoid, max_score_venture_sigmoid, max_score_foundations_sigmoid`

Filters supported by query params mirror the UI controls: `q, type, semester, creditsMin, creditsMax, available_programs, minSkills, minProduct, minVenture, minFoundations`, pagination `page, pageSize`, and sorting `course_name, credits, workload, score_*`.
