// importCsv.js
// Load environment variables from .env into process.env
require('dotenv').config({ quiet: true });
// Node core: file system
const fs = require('fs');
const path = require('path');
// CSV -> objects (sync parser)
const { parse } = require('csv-parse/sync');
// MySQL driver (promise API for async/await)
const mysql = require('mysql2/promise');

// Turn a cell value into an array of tags.
// Supports array-like strings (['a','b'] or ["a","b"]) and single values.
function splitTags(cell) {
  if (cell == null) return [];
  let cleaned = String(cell).trim();
  if (!cleaned) return [];

  // Parse array-like strings
  if (cleaned.startsWith('[') && cleaned.endsWith(']')) {
    const jsonish = cleaned.replace(/'/g, '"');
    try {
      const arr = JSON.parse(jsonish);
      if (Array.isArray(arr)) {
        return arr.map(x => String(x).trim()).filter(Boolean);
      }
    } catch (e) {
      // If parsing fails, fall through and treat as a single value
    }
  }

  // Treat everything else as a single tag value
  return [cleaned];
}

async function main() {
    // Read DB connection info & CSV path from env
    const {
        DB_HOST,
        DB_PORT,
        DB_USER,
        DB_PASS,
        DB_NAME,
        COURSES_CSV_PATH,
        SCORES_CSV_PATH
    } = process.env;

    const coursesCsvPath = COURSES_CSV_PATH;
    if (!coursesCsvPath) {
        throw new Error('Missing COURSES_CSV_PATH in environment');
    }

    // Create a small MySQL connection pool (fine for a few thousand rows)
    const pool = await mysql.createPool({
        host: DB_HOST,
        port: DB_PORT,
        user: DB_USER,
        password: DB_PASS,
        database: DB_NAME,
        waitForConnections: true,
        connectionLimit: 4,
        multipleStatements: false
    });

    // Read CSV file (into memory) and parse into rows (array of objects)
    const csv = fs.readFileSync(coursesCsvPath, 'utf8');
    const rows = parse(csv, { columns: true, skip_empty_lines: true, trim: true });
    console.log(`Loaded ${rows.length} rows`);

    let scoresByRowId = new Map();
    const scoresPath = SCORES_CSV_PATH || path.join(path.dirname(coursesCsvPath), 'courses_scores.csv');
    try {
        const scoresCsv = fs.readFileSync(scoresPath, 'utf8');
        const scoreRows = parse(scoresCsv, { columns: true, skip_empty_lines: true, trim: true });
        const toNum = (value) => {
            if (value == null || value === '') return null;
            const num = Number(value);
            return Number.isFinite(num) ? num : null;
        };
        for (const scoreRow of scoreRows) {
            const rowId = (scoreRow.row_id || '').toString().trim();
            if (!rowId) continue;
            scoresByRowId.set(rowId, {
                skills: toNum(scoreRow.score_skills_sigmoid),
                product: toNum(scoreRow.score_product_sigmoid),
                venture: toNum(scoreRow.score_venture_sigmoid),
                foundations: toNum(scoreRow.score_foundations_sigmoid),
            });
        }
        console.log(`Loaded ${scoresByRowId.size} score rows from ${scoresPath}`);
    } catch (err) {
        console.warn(`Could not load scores CSV at ${scoresPath}: ${err.message}`);
        scoresByRowId = new Map();
    }

    // Get (or create) a tag type ID by name.
    // Trick: ON DUPLICATE KEY + LAST_INSERT_ID lets us return the existing id on conflict.
    async function getTypeId(conn, typeName) {
        const [r] = await conn.execute(
        `INSERT INTO tag_types (name) VALUES (?)
        ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)`,
        [typeName]
        );
        return r.insertId;
    }

    // Get (or create) a concrete tag ID by (type, name).
    async function getTagId(conn, typeId, tagName) {
        const [r] = await conn.execute(
        `INSERT INTO tags (tag_type_id, name) VALUES (?, ?)
        ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)`,
        [typeId, tagName]
        );
        return r.insertId;
    }

    for (let i = 0; i < rows.length; i++) {
        const row = rows[i];

        // Map header names from the new CSV format
        // courses table columns (descriptive fields)
        const ROW_ID_COL = 'row_id';
        const COURSE_CODE_COL = 'course_code';
        const COURSE_NAME_COL = 'course_name';
        const URL_COL = 'course_url';
        const PROF_COL = 'prof_name';
        const CREDITS_COL = 'credits';
        const SEMESTER_COL = 'semester';
        const EXAM_FORM_COL = 'exam_form';
        const WORKLOAD_COL = 'workload';
        const TYPE_COL = 'type';
        const LANG_COL = 'lang';
        const SECTION_COL = 'section';

        // Filter tag columns: keep only these in tags/tag_types
        // (keywords and available_programs may be list-like values)
        const TAG_TYPE_COLUMNS = [
          'keywords',
          'available_programs'
        ];

        const courseCode = (row[COURSE_CODE_COL] || '').toString().trim();
        const courseName = (row[COURSE_NAME_COL] || '').toString().trim();
        const url = ((row[URL_COL] || '').toString().trim()) || null;
        const profName = ((row[PROF_COL] || '').toString().trim()) || null;

        // credits is an integer; default to 0 if not parseable
        let creditsRaw = (row[CREDITS_COL] ?? '').toString().trim();
        let credits = parseInt(creditsRaw, 10);
        if (!Number.isFinite(credits)) credits = 0; // ensure NOT NULL

        const semester = ((row[SEMESTER_COL] || '').toString().trim()) || null;
        const examForm = ((row[EXAM_FORM_COL] || '').toString().trim()) || null;
        const workload = ((row[WORKLOAD_COL] || '').toString().trim()) || null;

        let typeRaw = (row[TYPE_COL] || '').toString().trim().toLowerCase();
        let courseType = null;
        if (typeRaw === 'mandatory' || typeRaw === 'optional') {
          courseType = typeRaw;
        } else if (typeRaw) {
          // Try to coerce common variants
          if (/(compulsory|required|core)/i.test(typeRaw)) courseType = 'mandatory';
          else if (/(elective|optional)/i.test(typeRaw)) courseType = 'optional';
        }

        // NOT NULL fallbacks for normalized schema
        const lang = ((row[LANG_COL] || '').toString().trim()) || 'unknown';
        const section = ((row[SECTION_COL] || '').toString().trim()) || null; // section may be null; we only insert offering if present
        const rowId = ((row[ROW_ID_COL] || '').toString().trim());

        if (!rowId) {
            console.warn(`Row ${i + 1} has no row_id; skipped`);
            continue;
        }

        if (!courseName) {
            console.warn(`Row ${i + 1} has no course_name; skipped`);
            continue;
        }

        // Use one connection and a transaction per row for consistency
        const conn = await pool.getConnection();
        try {
            await conn.beginTransaction();

            // Upsert course into normalized schema (unique by course_code) and get id
            const [cr] = await conn.execute(
              `INSERT INTO courses (course_name, course_code, course_url, credits, lang, semester, exam_form, workload)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON DUPLICATE KEY UPDATE
                 course_name = VALUES(course_name),
                 course_url  = VALUES(course_url),
                 credits     = VALUES(credits),
                 lang        = VALUES(lang),
                 semester    = VALUES(semester),
                 exam_form   = VALUES(exam_form),
                 workload    = VALUES(workload),
                 id = LAST_INSERT_ID(id)`,
              [courseName, courseCode, url, credits, lang, semester || 'unknown', examForm, workload]
            );

            const courseId = cr.insertId;

            if (section) {
              const score = scoresByRowId.get(rowId) || {};
              const skillsScore = score.skills ?? null;
              const productScore = score.product ?? null;
              const ventureScore = score.venture ?? null;
              const foundationsScore = score.foundations ?? null;

              await conn.execute(
                `INSERT INTO course_offerings (
                   course_id,
                   row_id,
                   section,
                   type,
                   prof_name,
                   score_skills_sigmoid,
                   score_product_sigmoid,
                   score_venture_sigmoid,
                   score_foundations_sigmoid
                 )
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                 ON DUPLICATE KEY UPDATE
                   course_id = VALUES(course_id),
                   section = VALUES(section),
                   type = VALUES(type),
                   prof_name = VALUES(prof_name),
                   score_skills_sigmoid = VALUES(score_skills_sigmoid),
                   score_product_sigmoid = VALUES(score_product_sigmoid),
                   score_venture_sigmoid = VALUES(score_venture_sigmoid),
                   score_foundations_sigmoid = VALUES(score_foundations_sigmoid)`,
                [
                  courseId,
                  rowId,
                  section,
                  courseType,
                  profName,
                  skillsScore,
                  productScore,
                  ventureScore,
                  foundationsScore,
                ]
              );
            } else {
              console.warn(`Row ${i + 1} (${courseCode}) has no section; offering skipped`);
            }

            // For each selected column, treat its values as tags under that "type"
            for (const typeName of TAG_TYPE_COLUMNS) {
                const tagCells = splitTags(row[typeName]);
                if (!tagCells.length) continue;

                const typeId = await getTypeId(conn, typeName);

                for (const tagNameRaw of tagCells) {
                const tagName = tagNameRaw.trim();
                if (!tagName) continue;

                const tagId = await getTagId(conn, typeId, tagName);

                // Link course <-> tag (ignore duplicates)
                await conn.execute(
                    `INSERT IGNORE INTO course_tags (course_id, tag_id) VALUES (?, ?)`,
                    [courseId, tagId]
                );
                }
            }

            await conn.commit();
            if ((i + 1) % 100 === 0) console.log(`Imported ${i + 1}/${rows.length}`);
        } catch (e) {
            await conn.rollback();
            console.error(`Row ${i + 1} failed:`, e.message);
        } finally {
            conn.release();
        }
    }

    // Done with all rows
    await pool.end();
    console.log('Import complete ✅');
}

// Kick off the script and surface unhandled errors
main().catch(err => {
    console.error(err);
    process.exit(1);
});
