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

    // Build dynamic SQL parts
    const where = [];
    const paramsItems = []; // parameters for items query
    const paramsCount = []; // parameters for count query

    // Text search (also searches professor names through offerings)
    const hasQ = q && String(q).trim();
    if (hasQ) {
      where.push(`(
        c.course_name LIKE CONCAT('%', ?, '%') OR
        c.course_code LIKE CONCAT('%', ?, '%') OR
        c.exam_form   LIKE CONCAT('%', ?, '%') OR
        c.workload    LIKE CONCAT('%', ?, '%') OR
        EXISTS (
          SELECT 1 FROM course_offerings co_q
          WHERE co_q.course_id = c.id AND co_q.prof_name LIKE CONCAT('%', ?, '%')
        )
      )`);
      // same q used 5 times
      for (let i = 0; i < 5; i++) paramsItems.push(q.trim());
      for (let i = 0; i < 5; i++) paramsCount.push(q.trim());
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
      ? `\n  LEFT JOIN course_offerings co ON co.course_id = c.id`
      : '';

    // WHERE assembly
    const whereSQL = [
      where.length ? `(${where.join(' AND ')})` : null,
      tagOrBlocks.length ? `(${tagOrBlocks.join(' OR ')})` : null,
    ].filter(Boolean).join(' AND ');

    const whereClause = whereSQL ? `\nWHERE ${whereSQL}` : '';

    // GROUP BY (avoid duplicates due to joins) and HAVING for tag type coverage
    const groupBy = `\nGROUP BY c.id`;
    const having = tagFilters.length
      ? `\nHAVING ${tagFilters.map((_, i) => `SUM(tt.name = ?) > 0`).join(' AND ')}`
      : '';

    const havingParamsItems = tagFilters.map(([typeName]) => typeName);
    const havingParamsCount = tagFilters.map(([typeName]) => typeName);

    // Sorting
    const dir = String(sortOrder).toLowerCase() === 'asc' ? 'ASC' : 'DESC';
    let orderBy = `\nORDER BY c.course_name ASC`;

    // relevance: simple score using LIKE hits; only when q present
    const relevanceExpr = hasQ
      ? `(
          (c.course_name LIKE CONCAT('%', ?, '%')) * 5 +
          (c.course_code LIKE CONCAT('%', ?, '%')) * 5 +
          (c.exam_form   LIKE CONCAT('%', ?, '%')) * 2 +
          (c.workload    LIKE CONCAT('%', ?, '%')) * 1 +
          (CASE WHEN COUNT(DISTINCT co.prof_name) > 0 THEN 1 ELSE 0 END) * 3
        )`
      : '0';

    const relevanceParams = hasQ ? [q.trim(), q.trim(), q.trim(), q.trim()] : [];

    if (String(sortField) === 'relevance' && hasQ) {
      orderBy = `\nORDER BY ${relevanceExpr} ${dir}, c.course_name ASC`;
    } else if (String(sortField) === 'credits') {
      orderBy = `\nORDER BY c.credits ${dir}, c.course_name ASC`;
    } else if (String(sortField) === 'course_name') {
      orderBy = `\nORDER BY c.course_name ${dir}`;
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
        MIN(co.prof_name) AS prof_name,
        MIN(co.type)      AS type,
        GROUP_CONCAT(DISTINCT co.prof_name ORDER BY co.prof_name SEPARATOR ', ') AS prof_names,
        GROUP_CONCAT(DISTINCT co.type ORDER BY co.type SEPARATOR ', ')         AS offering_types
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
      ...relevanceParams,
    ];

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

    // Debug logs
    console.log('[courses] itemsSQL:', itemsSQL);
    console.log('[courses] itemsParams:', itemsParams);
    console.log('[courses] countSQL:', countSQL);
    console.log('[courses] countParams:', countParams);

    const [[countRow]] = await db.execute(countSQL, countParams);
    const total = Number(countRow?.total || 0);

    const [rows] = await db.execute(itemsSQL, itemsParams);

    return res.json({ items: rows, total, page: pageNum, pageSize: pageSizeNum });
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: 'failed to load courses' });
  }
});

module.exports = router;