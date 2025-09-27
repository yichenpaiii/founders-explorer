Supabase setup (Scheme A)

1) Create tables in Postgres (adapted from your MySQL schema): `courses`, `course_offerings`, `tags`, `tag_types`, `course_tags`.

2) Create the view `courses_search_view` used by the Cloudflare Pages Function.

- See `supabase/courses_search_view.sql.example` for a starting point.
- Ensure the view exposes the columns consumed by the UI: 
  `id, course_name, course_code, url, credits, lang, semester, exam_form, workload, prof_name, type, prof_names, offering_types, max_score_*_sigmoid, keywords[], available_programs[]`.

3) Permissions & RLS

- If the data is public read-only, keep tables locked and grant `SELECT` on the view to `anon` role only:

```sql
-- In the SQL editor (adjust schema/owner as needed)
grant usage on schema public to anon;
grant select on public.courses_search_view to anon;
```

- Keep RLS enabled and restrict base tables; expose only what you need through the view.

4) Performance

- Add indexes on `courses(course_code)`, `courses(semester)`, `course_offerings(course_id)`, and on score columns if needed.
- Consider a materialized view if queries become heavy; refresh via cron.

## Importing real course data

The repository includes a helper script to load the CSV output from `data-scraper` into Supabase via PostgREST.

1. Ensure you have generated the CSV files (`data-scraper/data/epfl_courses.csv` and `data-scraper/data/courses_scores.csv`).
2. Create a local env file for Supabase credentials:

   ```bash
   cp supabase/.env.example supabase/.env
   ```

   Fill `supabase/.env` with `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` (Project Settings → API).

3. Install the required Python dependency (inside your virtualenv):

   ```bash
   pip install requests
   ```

4. Run the import script. CLI flags become optional once `.env` is populated:

   ```bash
   python supabase/import_from_csv.py \
     --supabase-url https://YOUR_PROJECT.supabase.co \
     --service-role-key YOUR_SERVICE_ROLE_KEY
   ```

   - You may omit the flags after the first run; the script reads from `supabase/.env`.
   - The service role key is available under **Project Settings → API**.
   - The script is idempotent; re-running will upsert data based on unique keys (`course_code`, `row_id`, etc.).
5. After the script finishes, verify that `select * from public.courses_search_view limit 5;` returns rows.
