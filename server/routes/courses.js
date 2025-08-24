const express = require('express');
const router = express.Router();
const db = require('../db');

// GET /api/courses?q=keyword&lang=English,French&section=A&keywords=AI,ML&available_programs=CS,DS&page=1&pageSize=20
router.get('/', async (req, res) => {
  try {
    const { q, page = 1, pageSize = 50 } = req.query;

    // Only these are filter tags (others are descriptive in courses table)
    const ALLOWED_FILTER_TYPES = new Set(['lang', 'section', 'keywords', 'available_programs']);

    // Treat only ALLOWED_FILTER_TYPES as tag-type filters
    const rawFilters = Object.entries(req.query)
      .filter(([k]) => !['q', 'page', 'pageSize'].includes(k))
      .filter(([k]) => ALLOWED_FILTER_TYPES.has(k));

    // Parse each tag-type's values into an array
    const filters = rawFilters
      .map(([type, csv]) => [type, String(csv).split(',').map(s => s.trim()).filter(Boolean)])
      .filter(([, arr]) => arr.length);

    const params = [];
    const whereParts = [];

    // Keyword search on new columns
    if (q && String(q).trim()) {
      whereParts.push(`(c.course_name LIKE CONCAT('%', ?, '%'))`);
      params.push(q.trim());
    }

    // Build OR blocks (OR within the same type; AND across types via HAVING)
    const orBlocks = [];
    for (const [typeName, tagList] of filters) {
      orBlocks.push(`(tt.name = ? AND t.name IN (${Array(tagList.length).fill('?').join(',')}))`);
      params.push(typeName, ...tagList);
    }
    if (orBlocks.length) whereParts.push(orBlocks.join(' OR '));

    const limit = Math.max(1, Math.min(parseInt(pageSize, 10) || 20, 100));
    const offset = Math.max(0, ((parseInt(page, 10) || 1) - 1) * limit);

    // Defensive cast to numbers
    const lim = Number.isFinite(limit) ? Number(limit) : 20;
    const off = Number.isFinite(offset) ? Number(offset) : 0;

    // For HAVING: compute a per-type hit counter
    const selectHits = filters
      .map(([,], idx) => `SUM(tt.name = ? ) AS hit_${idx}`)
      .join(', ');

    // Add each typeName again for selectHits placeholders
    const hitParams = filters.map(([typeName]) => typeName);

    // Base SELECT now returns descriptive fields from the courses table
    const baseSelect = `SELECT c.id, c.course_name, c.course_code, c.url, c.prof_name, c.credits, c.semester, c.exam_form, c.workload, c.type`;

    // Build FROM/JOINS conditionally to avoid duplicate rows when no tag filters
    const fromAndJoins = filters.length
      ? `FROM courses c\nJOIN course_tags ct ON ct.course_id = c.id\nJOIN tags t        ON t.id = ct.tag_id\nJOIN tag_types tt  ON tt.id = t.tag_type_id`
      : `FROM courses c`;

    const whereSQL = whereParts.length ? `WHERE ${whereParts.join(' AND ')}` : '';

    const groupBySQL = filters.length ? `GROUP BY c.id` : '';
    const havingSQL = filters.length ? `HAVING ${filters.map((_, i) => `hit_${i} > 0`).join(' AND ')}` : '';

    const selectSQL = filters.length ? `${baseSelect}, ${selectHits}` : baseSelect;

    const sql = `\n      ${selectSQL}\n      ${fromAndJoins}\n      ${whereSQL}\n      ${groupBySQL}\n      ${havingSQL}\n      ORDER BY c.id DESC\n      LIMIT ${lim} OFFSET ${off}\n    `;

    // Params order must follow the appearance of "?" in SQL:
    // 1) selectHits (hitParams), 2) WHERE parts (params)
    const allParams = [...hitParams, ...params];
    console.log('SQL to run:', sql);
    console.log('Query params:', allParams);
    const [rows] = await db.execute(sql, allParams);
    res.json({ items: rows, page: Number(page), pageSize: limit });
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: 'failed to load courses' });
  }
});

module.exports = router;