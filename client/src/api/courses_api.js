/* global __SUPABASE_DEV_VARS__ */

import { createClient } from '@supabase/supabase-js';

const VIEW = 'courses_search_view';

let cachedClient = null;
let cachedClientKey = '';

export async function getCourses(options = {}) {
  const {
    page = 1,
    pageSize = 30,
    q,
    type,
    semester,
    creditsMin,
    creditsMax,
    availablePrograms,
    level,
    major,
    minor,
    minorLabel,
    degree,
    sortField,
    sortOrder,
    minSkills,
    minProduct,
    minVenture,
    minFoundations,
  } = options;

  const { supabaseUrl, supabaseAnonKey } = resolveSupabaseConfig();
  const supabase = ensureSupabaseClient(supabaseUrl, supabaseAnonKey);

  const resolvedPageSize = clampPageSize(pageSize);
  const resolvedPage = clampPage(page);
  const offset = (resolvedPage - 1) * resolvedPageSize;
  const rangeEnd = offset + resolvedPageSize - 1;

  let query = supabase.from(VIEW).select('*', { count: 'exact' });

  const searchClause = buildSearchClause(q);
  if (searchClause) {
    query = query.or(searchClause);
  }

  if (type) {
    query = query.eq('type', String(type));
  }

  if (semester) {
    query = query.eq('semester', String(semester));
  }

  const minCredits = parseNumberFilter(creditsMin);
  if (minCredits != null) {
    query = query.gte('credits', minCredits);
  }

  const maxCredits = parseNumberFilter(creditsMax);
  if (maxCredits != null) {
    query = query.lte('credits', maxCredits);
  }

  const programList = parseListFilter(availablePrograms);
  if (programList.length) {
    query = query.overlaps('available_programs', programList);
  }

  const degreeValue = typeof degree === 'string' ? degree.trim() : '';
  const levelValue = typeof level === 'string' ? level.trim() : '';
  const majorValue = typeof major === 'string' ? major.trim() : '';
  const minorProgram = typeof minor === 'string' ? minor.trim() : '';
  const baseMinorLabel = typeof minorLabel === 'string' ? minorLabel.trim() : '';

  const inferredMinorLevel = inferMinorSeasonLabel(degreeValue, levelValue);
  const resolvedMinorLabel = baseMinorLabel || (minorProgram && inferredMinorLevel ? `${inferredMinorLevel} ${minorProgram}` : '');
  let unionApplied = false;

  if (majorValue && minorProgram && degreeValue === 'MA' && levelValue && inferredMinorLevel) {
    const comboA = `and(available_levels.cs.${toPgArray([levelValue])},available_programs.cs.${toPgArray([majorValue])})`;
    const comboBParts = [
      `available_levels.cs.${toPgArray([inferredMinorLevel])}`,
      `available_programs.cs.${toPgArray([minorProgram])}`,
    ];
    if (resolvedMinorLabel) {
      comboBParts.push(`available_program_labels.cs.${toPgArray([resolvedMinorLabel])}`);
    }
    const comboB = `and(${comboBParts.join(',')})`;
    query = query.or(`${comboA},${comboB}`);
    unionApplied = true;
  }

  if (!unionApplied) {
    if (levelValue) {
      query = query.contains('available_levels', [levelValue]);
    }
    if (majorValue) {
      query = query.contains('available_programs', [majorValue]);
    }
    if (minorProgram) {
      if (inferredMinorLevel) {
        query = query.contains('available_levels', [inferredMinorLevel]);
      }
      query = query.contains('available_programs', [minorProgram]);
    }
    if (resolvedMinorLabel) {
      query = query.contains('available_program_labels', [resolvedMinorLabel]);
    }
  }

  const minSkillsVal = normalizeScoreFilter(minSkills);
  if (minSkillsVal != null) {
    query = query.gte('max_score_skills_sigmoid', minSkillsVal);
  }

  const minProductVal = normalizeScoreFilter(minProduct);
  if (minProductVal != null) {
    query = query.gte('max_score_product_sigmoid', minProductVal);
  }

  const minVentureVal = normalizeScoreFilter(minVenture);
  if (minVentureVal != null) {
    query = query.gte('max_score_venture_sigmoid', minVentureVal);
  }

  const minFoundationsVal = normalizeScoreFilter(minFoundations);
  if (minFoundationsVal != null) {
    query = query.gte('max_score_foundations_sigmoid', minFoundationsVal);
  }

  const orderColumn = mapSortField(sortField);
  const ascending = String(sortOrder).toLowerCase() === 'asc';

  if (orderColumn) {
    query = query.order(orderColumn, { ascending, nullsFirst: ascending });
  } else {
    query = query.order('course_name', { ascending: true });
  }

  query = query.range(offset, rangeEnd);

  const { data, count, error } = await query;

  if (error) {
    throw new Error(`Supabase request failed: ${error.message}`);
  }

  if (typeof console !== 'undefined') {
    const itemsCount = Array.isArray(data) ? data.length : 0;
    console.log(`[supabase] Retrieved ${itemsCount} rows from ${VIEW} (page ${resolvedPage}, total ${count ?? 'unknown'})`);
    try {
      console.log(JSON.stringify(data, null, 2));
    } catch {
      console.log(data);
    }
  }

  return {
    items: data ?? [],
    total: typeof count === 'number' ? count : (Array.isArray(data) ? data.length : 0),
    page: resolvedPage,
    pageSize: resolvedPageSize,
  };
}

function ensureSupabaseClient(url, anonKey) {
  const normalizedUrl = url.replace(/\/$/, '');
  const cacheKey = `${normalizedUrl}::${anonKey}`;

  if (!cachedClient || cachedClientKey !== cacheKey) {
    cachedClient = createClient(normalizedUrl, anonKey, {
      auth: {
        persistSession: false,
        autoRefreshToken: false,
        detectSessionInUrl: false,
      },
    });
    cachedClientKey = cacheKey;
  }

  return cachedClient;
}

function resolveSupabaseConfig() {
  const devVarsRaw = typeof __SUPABASE_DEV_VARS__ !== 'undefined' ? __SUPABASE_DEV_VARS__ : {};
  const devVars = typeof devVarsRaw === 'string' ? safeParseJson(devVarsRaw) : devVarsRaw;
  const supabaseUrl = readEnvString('SUPABASE_URL') || devVars.SUPABASE_URL || '';
  const supabaseAnonKey = readEnvString('SUPABASE_ANON_KEY') || devVars.SUPABASE_ANON_KEY || '';

  if (!supabaseUrl || !supabaseAnonKey) {
    throw new Error('Supabase environment variables are not configured');
  }

  return { supabaseUrl, supabaseAnonKey };
}

function buildSearchClause(rawValue) {
  if (typeof rawValue !== 'string') return '';
  const trimmed = rawValue.trim();
  if (!trimmed) return '';

  const sanitized = trimmed
    .replace(/[^a-zA-Z0-9\s._-]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

  if (!sanitized) return '';

  const pattern = `%${sanitized}%`;
  const filters = [
    `course_name.ilike.${pattern}`,
    `course_code.ilike.${pattern}`,
    `prof_name.ilike.${pattern}`,
    `prof_names.ilike.${pattern}`,
    `exam_form.ilike.${pattern}`,
    `workload.ilike.${pattern}`,
    `type.ilike.${pattern}`,
    `offering_types.ilike.${pattern}`,
  ];

  return filters.join(',');
}

function normalizeScoreFilter(value) {
  if (value == null || value === '') return null;
  const num = Number(value);
  if (!Number.isFinite(num) || num <= 0) return null;
  if (num >= 1) return 1;
  return num;
}

function toPgArray(values) {
  return `{${values.map((val) => `"${String(val).replace(/"/g, '\\"')}"`).join(',')}}`;
}

function parseNumberFilter(value) {
  if (value == null || value === '') return null;
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

function parseListFilter(value) {
  if (Array.isArray(value)) {
    return value.map((item) => String(item).trim()).filter(Boolean);
  }

  if (typeof value === 'string') {
    return value
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean);
  }

  return [];
}

function inferMinorSeasonLabel(degree, level) {
  if (degree !== 'MA') return '';
  if (!level) return '';
  const match = level.match(/MA(\d+)/i);
  if (match) {
    const idx = Number(match[1]);
    if (Number.isFinite(idx)) {
      return idx % 2 === 1 ? 'Minor Autumn Semester' : 'Minor Spring Semester';
    }
  }
  const lower = level.toLowerCase();
  if (lower.includes('autumn')) return 'Minor Autumn Semester';
  if (lower.includes('spring')) return 'Minor Spring Semester';
  return '';
}

function mapSortField(field) {
  switch (String(field)) {
    case 'credits':
      return 'credits';
    case 'workload':
      return 'workload';
    case 'score_skills':
      return 'max_score_skills_sigmoid';
    case 'score_product':
      return 'max_score_product_sigmoid';
    case 'score_venture':
      return 'max_score_venture_sigmoid';
    case 'score_foundations':
      return 'max_score_foundations_sigmoid';
    case 'course_name':
      return 'course_name';
    default:
      return null;
  }
}

function readEnvString(key) {
  const raw = typeof import.meta !== 'undefined' && import.meta.env ? import.meta.env[key] : undefined;
  return typeof raw === 'string' ? raw.trim() : '';
}

function safeParseJson(source) {
  try {
    return JSON.parse(source);
  } catch {
    return {};
  }
}

function clampPageSize(value) {
  const num = Number(value);
  if (!Number.isFinite(num) || num <= 0) return 30;
  return Math.min(Math.trunc(num), 100);
}

function clampPage(value) {
  const num = Number(value);
  if (!Number.isFinite(num) || num < 1) return 1;
  return Math.trunc(num);
}
