const express = require('express');
const router = express.Router();
const db = require('../db');

// GET /api/courses?q=keyword&lang=English,French&semester=winter&page=1&pageSize=20
router.get('/', async (req, res) => {
  try {
    const { q, page = 1, pageSize = 20 } = req.query;

    // Treat all query params except q/page/pageSize as tag-type filters
    const rawFilters = Object.entries(req.query)
      .filter(([k]) => !['q', 'page', 'pageSize'].includes(k));

    // Parse each tag-type's values into an array
    const filters = rawFilters
      .map(([type, csv]) => [type, String(csv).split(',').map(s => s.trim()).filter(Boolean)])
      .filter(([, arr]) => arr.length);

    const params = [];
    const whereParts = [];

    // Keyword search (LIKE). For speed, add FULLTEXT on courses(title, description)
    if (q && String(q).trim()) {
      whereParts.push(`(c.title LIKE CONCAT('%', ?, '%') OR c.description LIKE CONCAT('%', ?, '%'))`);
      params.push(q.trim(), q.trim());
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

    const havingParts = filters.map(() => 'SUM(1) > 0'); // placeholder note (hits are computed via aliases)

    // For HAVING: compute a per-type hit counter
    const selectHits = filters
      .map(([typeName], idx) => `SUM(tt.name = ? ) AS hit_${idx}`)
      .join(', ');

    // Add each typeName again for selectHits placeholders
    const hitParams = filters.map(([typeName]) => typeName);

    const sql = `
      SELECT c.id, c.title, c.description
      ${filters.length ? `, ${selectHits}` : ''}
      FROM courses c
      JOIN course_tags ct ON ct.course_id = c.id
      JOIN tags t        ON t.id = ct.tag_id
      JOIN tag_types tt  ON tt.id = t.tag_type_id
      ${whereParts.length ? `WHERE ${whereParts.join(' AND ')}` : ''}
      GROUP BY c.id
      ${filters.length ? `HAVING ${filters.map((_, i) => `hit_${i} > 0`).join(' AND ')}` : ''}
      ORDER BY c.id DESC
      LIMIT ${lim} OFFSET ${off}
    `;

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