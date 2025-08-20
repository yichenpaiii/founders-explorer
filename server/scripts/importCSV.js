// importCsv.js
// Load environment variables from .env into process.env
require('dotenv').config();
// Node core: file system
const fs = require('fs');
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
        DB_HOST, DB_PORT, DB_USER, DB_PASS, DB_NAME, CSV_PATH
    } = process.env;

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
    const csv = fs.readFileSync(CSV_PATH, 'utf8');
    const rows = parse(csv, { columns: true, skip_empty_lines: true, trim: true });
    console.log(`Loaded ${rows.length} rows`);

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

        // Map new header names:
        // title  <- course_name
        // description <- a compact summary built from several fields
        // tag types <- choose the columns below to act as tag categories
        const TITLE_COL = 'course_name';
        const DESCRIPTION_COLS = ['keywords', 'exam_form', 'semester', 'prof_name', 'course_url'];

        // Columns treated as tag "types" (category name = column header)
        // You can tweak this list anytime. We intentionally skip identifiers/URLs.
        const TAG_TYPE_COLUMNS = [
        'lang',
        'program_term',
        'section',
        'semester',
        'credits',
        'type',
        'keywords',
        'available_programs'
        ];

        const title = (row[TITLE_COL] || '').trim();
        const description = DESCRIPTION_COLS
        .map(k => (row[k] || '').toString().trim())
        .filter(Boolean)
        .join('\n') || null;

        if (!title) {
            console.warn(`Row ${i + 1} has no course_name; skipped`);
            continue;
        }

        // Use one connection and a transaction per row for consistency
        const conn = await pool.getConnection();
        try {
            await conn.beginTransaction();

            // Insert the course and capture its ID
            const [cr] = await conn.execute(
                `INSERT INTO courses (title, description) VALUES (?, ?)`,
                [title, description]
            );
            const courseId = cr.insertId;

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