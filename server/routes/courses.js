const express = require('express');
const router = express.Router();
const db = require('../db');

// GET /api/courses
// Query params:
//   q                : string (search in course_name, course_code, exam_form, workload, prof_name)
//   type             : 'mandatory' | 'optional' (section-level; filter via course_offerings)
//   section          : string (optional, filters via course_offerings)
//   semester         : string (e.g., 'winter' | 'summer')
//   creditsMin       : number
//   creditsMax       : number
//   keywords         : CSV list of tag names (tags under tag_type 'keywords')
//   available_programs : CSV list of tag names (tags under tag_type 'available_programs')
//   sortField        : 'relevance' | 'course_name' | 'credits'
//   sortOrder        : 'asc' | 'desc'
//   page             : 1-based page index
//   pageSize         : items per page
router.get('/', async (req, res) => {
  try {
    const {
      q = '',
      type = '',
      section = '',
      semester = '',
      creditsMin = '',
      creditsMax = '',
      keywords = '',
      available_programs = '',
      sortField = 'relevance',
      sortOrder = 'desc',
      page = 1,
      pageSize = 20,
      minSkills = '',
      minProduct = '',
      minVenture = '',
      minFoundations = '',
    } = req.query;

    const pageNum = Math.max(1, parseInt(page, 10) || 1);
    const pageSizeNum = Math.max(1, Math.min(parseInt(pageSize, 10) || 20, 100));
    const lim = pageSizeNum;
    const off = (pageNum - 1) * pageSizeNum;

    // Parse CSV -> arrays
    const parseCSV = (val) => String(val || '')
      .split(',')
      .map(s => s.trim())
      .filter(Boolean);

    const tagFilters = [
      ['keywords', parseCSV(keywords)],
      ['available_programs', parseCSV(available_programs)],
    ].filter(([, arr]) => arr.length);

    const hasQ = q && String(q).trim();

    const clampScore = (val) => {
      if (val === '' || val == null) return null;
      const num = Number(val);
      if (!Number.isFinite(num)) return null;
      if (num < 0) return 0;
      if (num > 1) return 1;
      return num;
    };

    const minScoreFilters = {
      skills: clampScore(minSkills),
      product: clampScore(minProduct),
      venture: clampScore(minVenture),
      foundations: clampScore(minFoundations),
    };

    // Build dynamic SQL parts
    const where = [];
    const paramsItems = []; // parameters for items query
    const paramsCount = []; // parameters for count query

    if (hasQ) {
      const trimmedQ = q.trim();
      const baseClause = `(
        c.course_name LIKE CONCAT('%', ?, '%') OR
        c.course_code LIKE CONCAT('%', ?, '%') OR
        c.exam_form   LIKE CONCAT('%', ?, '%') OR
        c.workload    LIKE CONCAT('%', ?, '%') OR
        EXISTS (
          SELECT 1 FROM course_offerings co_q
          WHERE co_q.course_id = c.id AND co_q.prof_name LIKE CONCAT('%', ?, '%')
        )
      )`;

      const textParams = [trimmedQ, trimmedQ, trimmedQ, trimmedQ, trimmedQ];

      where.push(baseClause);
      paramsItems.push(...textParams);
      paramsCount.push(...textParams);
    }

    // Semester filter (course-level)
    if (semester) {
      where.push(`LOWER(c.semester) = LOWER(?)`);
      paramsItems.push(semester);
      paramsCount.push(semester);
    }

    // Credits range (course-level)
    if (creditsMin !== '') {
      where.push(`c.credits >= ?`);
      paramsItems.push(Number(creditsMin));
      paramsCount.push(Number(creditsMin));
    }
    if (creditsMax !== '') {
      where.push(`c.credits <= ?`);
      paramsItems.push(Number(creditsMax));
      paramsCount.push(Number(creditsMax));
    }

    // Offering-level filters: type, section
    const needOfferingsJoin = true; // always join offerings so we can expose prof_name/type aggregates safely

    if (type) {
      where.push(`EXISTS (
        SELECT 1 FROM course_offerings co_t
        WHERE co_t.course_id = c.id AND co_t.type = ?
      )`);
      paramsItems.push(type);
      paramsCount.push(type);
    }

    if (section) {
      where.push(`EXISTS (
        SELECT 1 FROM course_offerings co_s
        WHERE co_s.course_id = c.id AND co_s.section = ?
      )`);
      paramsItems.push(section);
      paramsCount.push(section);
    }

    // Tag filters (AND across types, OR within a type)
    // Implemented via HAVING counts on joined tags per type
    const tagOrBlocks = []; // for WHERE, to limit join rows early
    const tagParamsItems = [];
    const tagParamsCount = [];

    for (const [typeName, names] of tagFilters) {
      // (tt.name = ? AND t.name IN (?, ?, ...))
      const ph = names.map(() => '?').join(',');
      tagOrBlocks.push(`(tt.name = ? AND t.name IN (${ph}))`);
      tagParamsItems.push(typeName, ...names);
      tagParamsCount.push(typeName, ...names);
    }

    // Base FROM and conditional JOINS
    const joinsForTags = tagFilters.length
      ? `\n  JOIN course_tags ct ON ct.course_id = c.id\n  JOIN tags t        ON t.id = ct.tag_id\n  JOIN tag_types tt  ON tt.id = t.tag_type_id`
      : '';

    const joinOfferings = needOfferingsJoin
      ? `\n  LEFT JOIN (\n    SELECT\n      co.course_id,\n      COALESCE(\n        JSON_ARRAYAGG(\n          JSON_OBJECT(\n            'row_id', co.row_id,\n            'section', co.section,\n            'type', co.type,\n            'prof_name', co.prof_name,\n            'score_skills_sigmoid', co.score_skills_sigmoid,\n            'score_product_sigmoid', co.score_product_sigmoid,\n            'score_venture_sigmoid', co.score_venture_sigmoid,\n            'score_foundations_sigmoid', co.score_foundations_sigmoid\n          )\n        ), JSON_ARRAY()\n      ) AS offerings_json,\n      MAX(co.score_skills_sigmoid)      AS max_score_skills_sigmoid,\n      MAX(co.score_product_sigmoid)     AS max_score_product_sigmoid,\n      MAX(co.score_venture_sigmoid)     AS max_score_venture_sigmoid,\n      MAX(co.score_foundations_sigmoid) AS max_score_foundations_sigmoid,\n      MIN(co.prof_name)                 AS primary_prof_name,\n      MIN(co.type)                      AS primary_type,\n      GROUP_CONCAT(DISTINCT co.prof_name ORDER BY co.prof_name SEPARATOR ', ') AS prof_names,\n      GROUP_CONCAT(DISTINCT co.type ORDER BY co.type SEPARATOR ', ')         AS offering_types\n    FROM course_offerings co\n    GROUP BY co.course_id\n  ) co ON co.course_id = c.id`
      : '';

    const aspectColumns = {
      skills: 'score_skills_sigmoid',
      product: 'score_product_sigmoid',
      venture: 'score_venture_sigmoid',
      foundations: 'score_foundations_sigmoid',
    };

    const scoreConditions = [];
    const scoreParams = [];
    for (const [aspect, minVal] of Object.entries(minScoreFilters)) {
      if (minVal != null && minVal > 0) {
        const column = aspectColumns[aspect];
        scoreConditions.push(`co_sf.${column} >= ?`);
        scoreParams.push(minVal);
      }
    }

    if (scoreConditions.length) {
      const scoreFilterSQL = `EXISTS (\n        SELECT 1\n        FROM course_offerings co_sf\n        WHERE co_sf.course_id = c.id\n          ${scoreConditions.map((cond) => `AND ${cond}`).join('\n          ')}\n      )`;
      where.push(scoreFilterSQL);
      paramsItems.push(...scoreParams);
      paramsCount.push(...scoreParams);
    }

    // WHERE assembly
    const whereSQL = [
      where.length ? `(${where.join(' AND ')})` : null,
      tagOrBlocks.length ? `(${tagOrBlocks.join(' OR ')})` : null,
    ].filter(Boolean).join(' AND ');

    const whereClause = whereSQL ? `\nWHERE ${whereSQL}` : '';

    // GROUP BY (avoid duplicates due to joins) and HAVING for tag type coverage
    const groupBy = `\nGROUP BY c.id`;
    const havingParts = [];
    const havingParamsItems = [];
    const havingParamsCount = [];

    if (tagFilters.length) {
      for (const [typeName] of tagFilters) {
        havingParts.push('SUM(tt.name = ?) > 0');
        havingParamsItems.push(typeName);
        havingParamsCount.push(typeName);
      }
    }

    const having = havingParts.length ? `\nHAVING ${havingParts.join(' AND ')}` : '';

    // Sorting
    const dir = String(sortOrder).toLowerCase() === 'asc' ? 'ASC' : 'DESC';
    let orderBy = `\nORDER BY c.course_name ASC`;

    // Workload numeric normalization compatible with MySQL 5.7+/MariaDB:
    // 1) Take prefix before 'hrs' as numeric candidate
    // 2) Validate numeric with REGEXP
    // 3) Convert semester totals to weekly equivalent by dividing by ~14
    const wlPrefix = `TRIM(SUBSTRING_INDEX(TRIM(COALESCE(c.workload, '')), 'hrs', 1))`;
    const wlIsNum = `${wlPrefix} REGEXP '^[0-9]+(\\.[0-9]+)?$'`;
    const wlNumericDec = `CASE WHEN ${wlIsNum} THEN CAST(${wlPrefix} AS DECIMAL(10,2)) ELSE NULL END`;
    const wlWeeklyEq = `CASE WHEN c.workload LIKE '%hrs/week%'
                              THEN ${wlNumericDec}
                              WHEN c.workload LIKE '%hrs/semester%'
                              THEN ${wlNumericDec} / 14
                              ELSE NULL END`;

    // relevance: simple score using LIKE hits; only when q present
    const relevanceExpr = hasQ
      ? `(
          (c.course_name LIKE CONCAT('%', ?, '%')) * 5 +
          (c.course_code LIKE CONCAT('%', ?, '%')) * 5 +
          (c.exam_form   LIKE CONCAT('%', ?, '%')) * 2 +
          (c.workload    LIKE CONCAT('%', ?, '%')) * 1 +
          (CASE WHEN co.prof_names IS NOT NULL AND co.prof_names <> '' THEN 1 ELSE 0 END) * 3
        )`
      : '0';

    const relevanceParams = hasQ ? [q.trim(), q.trim(), q.trim(), q.trim()] : [];

    if (String(sortField) === 'relevance' && hasQ) {
      orderBy = `\nORDER BY ${relevanceExpr} ${dir}, c.course_name ASC`;
    } else if (String(sortField) === 'credits') {
      orderBy = `\nORDER BY c.credits ${dir}, c.course_name ASC`;
    } else if (String(sortField) === 'workload') {
      orderBy = `\nORDER BY (${wlWeeklyEq} IS NULL) ASC, ${wlWeeklyEq} ${dir}, c.course_name ASC`;
    } else if (String(sortField) === 'course_name') {
      orderBy = `\nORDER BY c.course_name ${dir}`;
    } else if (String(sortField) === 'score_skills') {
      orderBy = dir === 'DESC'
        ? `\nORDER BY (co.max_score_skills_sigmoid IS NULL) ASC, co.max_score_skills_sigmoid DESC, c.course_name ASC`
        : `\nORDER BY c.course_name ASC`;
    } else if (String(sortField) === 'score_product') {
      orderBy = dir === 'DESC'
        ? `\nORDER BY (co.max_score_product_sigmoid IS NULL) ASC, co.max_score_product_sigmoid DESC, c.course_name ASC`
        : `\nORDER BY c.course_name ASC`;
    } else if (String(sortField) === 'score_venture') {
      orderBy = dir === 'DESC'
        ? `\nORDER BY (co.max_score_venture_sigmoid IS NULL) ASC, co.max_score_venture_sigmoid DESC, c.course_name ASC`
        : `\nORDER BY c.course_name ASC`;
    } else if (String(sortField) === 'score_foundations') {
      orderBy = dir === 'DESC'
        ? `\nORDER BY (co.max_score_foundations_sigmoid IS NULL) ASC, co.max_score_foundations_sigmoid DESC, c.course_name ASC`
        : `\nORDER BY c.course_name ASC`;
    }

    // Items query: return one row per course with some aggregates for display
    const itemsSQL = `
      SELECT
        c.id,
        c.course_name,
        c.course_code,
        c.course_url AS url,
        c.credits,
        c.lang,
        c.semester,
        c.exam_form,
        c.workload,
        co.primary_prof_name AS prof_name,
        co.primary_type      AS type,
        co.prof_names,
        co.offering_types,
        COALESCE(co.offerings_json, JSON_ARRAY()) AS offerings_json,
        co.max_score_skills_sigmoid,
        co.max_score_product_sigmoid,
        co.max_score_venture_sigmoid,
        co.max_score_foundations_sigmoid
      FROM courses c${joinOfferings}${joinsForTags}
      ${whereClause}
      ${groupBy}
      ${having}
      ${orderBy}
      LIMIT ${lim} OFFSET ${off}
    `;

    const itemsParams = [
      ...paramsItems,
      ...tagParamsItems,
      ...havingParamsItems,
    ];

    if (String(sortField) === 'relevance' && hasQ) {
      itemsParams.push(...relevanceParams);
    }

    // Count query: number of distinct courses matching the same filters
    const countSQL = `
      SELECT COUNT(*) AS total
      FROM (
        SELECT c.id
        FROM courses c${joinOfferings}${joinsForTags}
        ${whereClause}
        ${groupBy}
        ${having}
      ) x
    `;

    const countParams = [
      ...paramsCount,
      ...tagParamsCount,
      ...havingParamsCount,
    ];

    // Debug logs (enable by setting DEBUG_SQL=1)
    if (process.env.DEBUG_SQL === '1') {
      console.log('[courses] itemsSQL:', itemsSQL);
      console.log('[courses] itemsParams:', itemsParams);
      console.log('[courses] countSQL:', countSQL);
      console.log('[courses] countParams:', countParams);
    }

    const [[countRow]] = await db.execute(countSQL, countParams);
    const total = Number(countRow?.total || 0);

    const [rows] = await db.execute(itemsSQL, itemsParams);
    let mappedItems = rows.map((row) => {
      const { offerings_json: offeringsJson, ...rest } = row;
      let offerings = [];
      if (Array.isArray(offeringsJson)) {
        offerings = offeringsJson;
      } else if (typeof offeringsJson === 'string' && offeringsJson.trim()) {
        try {
          const parsed = JSON.parse(offeringsJson);
          if (Array.isArray(parsed)) offerings = parsed;
        } catch (err) {
          console.warn('[courses] failed to parse offerings_json', err.message);
        }
      } else if (offeringsJson && typeof offeringsJson === 'object') {
        // Some MySQL drivers return JSON objects as plain JS objects
        offerings = Object.values(offeringsJson);
      }
      return { ...rest, offerings };
    });

    return res.json({ items: mappedItems, total, page: pageNum, pageSize: pageSizeNum });
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: 'failed to load courses' });
  }
});

module.exports = router;
