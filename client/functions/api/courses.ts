// Cloudflare Pages Function for GET /api/courses
// Proxies to Supabase PostgREST view `courses_search_view`

export interface Env {
  SUPABASE_URL: string
  SUPABASE_ANON_KEY: string
}

type SortField =
  | 'relevance'
  | 'course_name'
  | 'credits'
  | 'workload'
  | 'score_skills'
  | 'score_product'
  | 'score_venture'
  | 'score_foundations'

const VIEW = 'courses_search_view';

export const onRequestGet: PagesFunction<Env> = async ({ request, env }) => {
  try {
    if (!env.SUPABASE_URL || !env.SUPABASE_ANON_KEY) {
      return jsonError(500, 'Supabase env not configured');
    }

    const url = new URL(request.url);
    const q = (url.searchParams.get('q') || '').trim();
    const type = (url.searchParams.get('type') || '').trim();
    const section = (url.searchParams.get('section') || '').trim(); // optional; requires view support
    const semester = (url.searchParams.get('semester') || '').trim();
    const creditsMin = valNum(url.searchParams.get('creditsMin'));
    const creditsMax = valNum(url.searchParams.get('creditsMax'));
    const availableProgramsParam = (url.searchParams.get('available_programs') || '').trim();
    const keywordsParam = (url.searchParams.get('keywords') || '').trim();
    const minSkills = clamp01(url.searchParams.get('minSkills'));
    const minProduct = clamp01(url.searchParams.get('minProduct'));
    const minVenture = clamp01(url.searchParams.get('minVenture'));
    const minFoundations = clamp01(url.searchParams.get('minFoundations'));
    const sortField = (url.searchParams.get('sortField') || 'course_name') as SortField;
    const sortOrder = (url.searchParams.get('sortOrder') || 'asc').toLowerCase() === 'desc' ? 'desc' : 'asc';
    const page = Math.max(1, valInt(url.searchParams.get('page')) || 1);
    const pageSize = Math.max(1, Math.min(valInt(url.searchParams.get('pageSize')) || 20, 100));
    const limit = pageSize;
    const offset = (page - 1) * pageSize;
    const debug = url.searchParams.get('debug') === '1';
    const debugSteps: string[] = [];
    const logStep = (label: string, value?: string | number | null) => {
      if (!debug) return;
      const message = value === undefined || value === null ? label : `${label}: ${String(value)}`;
      debugSteps.push(message);
      console.log(`[courses-debug] ${message}`);
    };

    // Build PostgREST query
    const rest = new URL(env.SUPABASE_URL.replace(/\/$/, '') + `/rest/v1/${VIEW}`);
    logStep('Initial Supabase URL', rest.toString());

    // Select the fields the UI consumes
    const select = [
      'id',
      'course_name',
      'course_code',
      'url',
      'credits',
      'lang',
      'semester',
      'exam_form',
      'workload',
      'prof_name',
      'type',
      'prof_names',
      'offering_types',
      'max_score_skills_sigmoid',
      'max_score_product_sigmoid',
      'max_score_venture_sigmoid',
      'max_score_foundations_sigmoid',
    ].join(',');
    rest.searchParams.set('select', select);
    logStep('Select columns', select);

    // Filters
    if (q) {
      // OR across several columns
      const term = `*${escapeIlike(q)}*`;
      const orExpr = `course_name.ilike.${term},course_code.ilike.${term},exam_form.ilike.${term},workload.ilike.${term},prof_names.ilike.${term}`;
      rest.searchParams.set('or', `(${orExpr})`);
      logStep('Applied search term', term);
    }

    if (semester) rest.searchParams.set('semester', `ilike.${escapeIlike(semester)}`);
    if (typeof creditsMin === 'number') rest.searchParams.set('credits', `gte.${creditsMin}`);
    if (typeof creditsMax === 'number') rest.searchParams.append('credits', `lte.${creditsMax}`);
    if (semester) logStep('Filter semester', semester);
    if (typeof creditsMin === 'number') logStep('Filter credits >=', creditsMin);
    if (typeof creditsMax === 'number') logStep('Filter credits <=', creditsMax);

    if (type) {
      // Prefer filtering by primary type if available
      rest.searchParams.set('type', `eq.${type}`);
      // Fallback/extra match on aggregated types string if present in view
      rest.searchParams.append('offering_types', `ilike.*${escapeIlike(type)}*`);
      logStep('Filter type', type);
    }

    if (section) {
      // Requires the view to expose either sections array or flattened text
      // We try both possible columns
      rest.searchParams.set('sections', `cs.{${escapePgArray(section)}}`);
      rest.searchParams.append('sections_text', `ilike.*${escapeIlike(section)}*`);
      logStep('Filter section', section);
    }

    // Array contains for tags if the view exposes arrays
    const toCsvArray = (raw: string) => raw.split(',').map(s => s.trim()).filter(Boolean);
    const programs = toCsvArray(availableProgramsParam);
    if (programs.length) {
      rest.searchParams.set('available_programs', `cs.{${programs.map(escapePgArray).join(',')}}`);
      logStep('Filter available_programs', programs.join(','));
    }
    const keywords = toCsvArray(keywordsParam);
    if (keywords.length) {
      rest.searchParams.set('keywords', `cs.{${keywords.map(escapePgArray).join(',')}}`);
      logStep('Filter keywords', keywords.join(','));
    }

    if (typeof minSkills === 'number') rest.searchParams.set('max_score_skills_sigmoid', `gte.${minSkills}`);
    if (typeof minProduct === 'number') rest.searchParams.set('max_score_product_sigmoid', `gte.${minProduct}`);
    if (typeof minVenture === 'number') rest.searchParams.set('max_score_venture_sigmoid', `gte.${minVenture}`);
    if (typeof minFoundations === 'number') rest.searchParams.set('max_score_foundations_sigmoid', `gte.${minFoundations}`);
    if (typeof minSkills === 'number') logStep('Filter minSkills', minSkills);
    if (typeof minProduct === 'number') logStep('Filter minProduct', minProduct);
    if (typeof minVenture === 'number') logStep('Filter minVenture', minVenture);
    if (typeof minFoundations === 'number') logStep('Filter minFoundations', minFoundations);

    // Sorting
    const orderMappings: Record<string, string> = {
      course_name: 'course_name',
      credits: 'credits',
      workload: 'workload', // if view provides numeric-normalized workload use that column instead
      score_skills: 'max_score_skills_sigmoid',
      score_product: 'max_score_product_sigmoid',
      score_venture: 'max_score_venture_sigmoid',
      score_foundations: 'max_score_foundations_sigmoid',
    };
    const mapped = orderMappings[sortField] || 'course_name';
    rest.searchParams.set('order', `${mapped}.${sortOrder}.nullslast`);
    logStep('Sort order', `${mapped}.${sortOrder}`);

    // Pagination via Range header (gives Content-Range with total when Prefer: count=exact)
    const rangeStart = offset;
    const rangeEnd = offset + limit - 1;
    logStep('Pagination', `${rangeStart}-${rangeEnd}`);

    const headers: Record<string, string> = {
      apikey: env.SUPABASE_ANON_KEY,
      Authorization: `Bearer ${env.SUPABASE_ANON_KEY}`,
      Prefer: 'count=exact',
    };

    // Edge cache (optional short TTL); bypass if search term provided or offset > 0
    const useCache = !debug && request.method === 'GET' && !q && offset === 0;
    const cacheKey = new Request(rest.toString(), { headers, method: 'GET' });
    if (useCache) {
      const cached = await caches.default.match(cacheKey);
      if (cached) {
        // Attach paging info based on cached Content-Range if present
        const total = parseTotalFromContentRange(cached.headers.get('Content-Range'));
        const data = await cached.json();
        return jsonOk({ items: data, total, page, pageSize }, { 'Cache-Control': 'public, max-age=60' });
      }
    }

    const upstreamReq = new Request(rest.toString(), {
      headers: {
        ...headers,
        'Range-Unit': 'items',
        Range: `${rangeStart}-${rangeEnd}`,
      },
      method: 'GET',
    });
    logStep('Supabase request URL', rest.toString());
    const resp = await fetch(upstreamReq);

    if (!resp.ok) {
      const text = await resp.text();
      logStep('Supabase error', `${resp.status} ${text || resp.statusText}`);
      return jsonError(resp.status, `Upstream error: ${text || resp.statusText}`);
    }

    const total = parseTotalFromContentRange(resp.headers.get('Content-Range'));
    logStep('Content-Range', resp.headers.get('Content-Range'));
    logStep('Total rows', total);
    const items = await resp.json();
    logStep('Items returned', items.length);

    if (useCache) {
      const cacheHeaders = new Headers(resp.headers);
      cacheHeaders.set('Cache-Control', 'public, max-age=60');
      const toCache = new Response(JSON.stringify(items), { status: 200, headers: cacheHeaders });
      // no await needed, but keep it deterministic
      await caches.default.put(cacheKey, toCache.clone());
    }

    const payload: Record<string, any> = { items, total, page, pageSize };
    if (debug) {
      payload.debug = debugSteps;
      payload.supabaseRequest = rest.toString();
    }
    return jsonOk(payload, { 'Cache-Control': 'public, max-age=30' });
  } catch (err: any) {
    return jsonError(500, err?.message || 'Internal error');
  }
};

function valInt(v: string | null): number | null {
  const n = Number(v);
  return Number.isFinite(n) ? Math.trunc(n) : null;
}
function valNum(v: string | null): number | null {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}
function clamp01(v: string | null): number | null {
  if (v == null || v === '') return null;
  const n = Number(v);
  if (!Number.isFinite(n)) return null;
  return Math.max(0, Math.min(1, n));
}
function escapeIlike(s: string): string {
  // Escape PostgREST ilike wildcards
  return s.replace(/[%,]/g, ch => ({ '%': '%25', ',': '%2C' }[ch]!));
}
function escapePgArray(s: string): string {
  // Basic escaping for Postgres array literal entries (no quotes to keep it simple)
  return s.replace(/[{}\\]/g, '');
}
function parseTotalFromContentRange(h: string | null): number {
  // Formats: "*/123" or "0-19/123"
  if (!h) return 0;
  const m = h.match(/\/(\d+)$/);
  return m ? Number(m[1]) : 0;
}
function jsonOk(body: any, extraHeaders?: Record<string, string>): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      ...extraHeaders,
    },
  });
}
function jsonError(status: number, message: string): Response {
  return new Response(JSON.stringify({ error: message }), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
  });
}
