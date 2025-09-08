import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { getCourses } from "../api/courses_api";  // adjust path if needed

const GRID_MIN_WIDTH = 220; // px

// Pareto helpers: maximize credits, minimize workload
function parseNumberLike(value) {
  if (typeof value === 'number') return value;
  if (typeof value !== 'string') return NaN;
  const m = value.match(/[-+]?[0-9]*\.?[0-9]+/);
  return m ? Number(m[0]) : NaN;
}

function creditsOf(c) {
  const n = parseNumberLike(c?.credits);
  return Number.isFinite(n) ? n : 0; // default low credits if missing
}

function workloadOf(c) {
  const n = parseNumberLike(c?.workload);
  return Number.isFinite(n) ? n : Number.POSITIVE_INFINITY; // default very high if missing
}

function dominates(a, b, pref) {
  // pref: { credits: 'max'|'min', workload: 'max'|'min' }
  const cmp = (va, vb, want) => want === 'max' ? (va >= vb) : (va <= vb);
  const strict = (va, vb, want) => want === 'max' ? (va > vb) : (va < vb);
  const betterOrEqualCredits = cmp(a.credits, b.credits, pref.credits);
  const betterOrEqualWork = cmp(a.workload, b.workload, pref.workload);
  const oneStrict = strict(a.credits, b.credits, pref.credits) || strict(a.workload, b.workload, pref.workload);
  return betterOrEqualCredits && betterOrEqualWork && oneStrict;
}

function computeParetoRanks(items, pref) {
  // items: array of { idx, credits, workload }
  const n = items.length;
  const dominatedByCount = new Array(n).fill(0);
  const dominatesList = Array.from({ length: n }, () => []);

  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      if (i === j) continue;
      if (dominates(items[i], items[j], pref)) {
        dominatesList[i].push(j);
      } else if (dominates(items[j], items[i], pref)) {
        dominatedByCount[i]++;
      }
    }
  }

  const fronts = [];
  let current = [];
  for (let i = 0; i < n; i++) if (dominatedByCount[i] === 0) current.push(i);
  let rank = 0;
  const ranks = new Array(n).fill(Infinity);
  while (current.length) {
    fronts.push(current);
    const next = [];
    for (const i of current) {
      ranks[i] = rank;
      for (const j of dominatesList[i]) {
        dominatedByCount[j]--;
        if (dominatedByCount[j] === 0) next.push(j);
      }
    }
    current = next;
    rank++;
  }
  return ranks; // if some remain Infinity (shouldn't), treat as worst
}

function colorForRank(rank, maxRank) {
  const baseHue = 210; // blue
  const sat = 70; // percent
  const minL = 25; // darkest for best
  const maxL = 90; // lightest for worst
  const t = maxRank <= 0 ? 0 : rank / maxRank; // 0..1
  const l = Math.round(minL + t * (maxL - minL));
  return `hsl(${baseHue} ${sat}% ${l}%)`;
}

function textColorForBgHslLightness(lightness) {
  // simple contrast heuristic
  return lightness < 55 ? '#fff' : '#111';
}

function CoursesList() {
  const location = useLocation();
  const [courses, setCourses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [showFilters, setShowFilters] = useState(true);
  const [filters, setFilters] = useState({ query: "", type: "", semester: "", creditsMin: "", creditsMax: "" });
  const [sortField, setSortField] = useState("");
  const [sortOrder, setSortOrder] = useState("asc");
  const [viewMode, setViewMode] = useState("list"); // 'list' | 'grid'
  const [paretoPref, setParetoPref] = useState({ credits: 'max', workload: 'min' }); // 'max'|'min' for each

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      setError(null);
      try {
        const sp = new URLSearchParams(location.search);
        const ap = sp.get('available_programs') || '';
        const params = {
          page,
          pageSize,
          // map UI filters to backend query params
          q: filters.query || undefined,
          type: filters.type || undefined,
          semester: filters.semester || undefined,
          creditsMin: filters.creditsMin !== "" ? Number(filters.creditsMin) : undefined,
          creditsMax: filters.creditsMax !== "" ? Number(filters.creditsMax) : undefined,
          availablePrograms: ap || undefined,
          sortField: sortField || undefined,
          sortOrder: sortField ? sortOrder : undefined,
        };
        const data = await getCourses(params);
        console.log("API response:", data);
        setCourses(data.items || []);
      } catch (err) {
        setError(err?.message || "Failed to load courses");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [page, pageSize, filters, location.search, sortField, sortOrder]);

  useEffect(() => {
    setPage(1);
  }, [filters.query, filters.type, filters.semester, filters.creditsMin, filters.creditsMax, location.search, sortField, sortOrder]);

  return (
    <div style={{ display: "flex", gap: "1rem" }}>
      {/* Left Filter Bar */}
      <aside
        style={{
          width: showFilters ? 260 : 0,
          transition: "width 0.2s ease",
          position: "sticky",
          top: 0,
          height: "100vh",
          alignSelf: "flex-start",
          overflowY: showFilters ? "auto" : "hidden",
          overflowX: "hidden",
          borderRight: "1px solid #eee",
          paddingRight: showFilters ? "1rem" : 0,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3 style={{ margin: 0 }}>Filters</h3>
          <button onClick={() => setShowFilters(false)}>Hide</button>
        </div>
        <div style={{ display: "grid", gap: "0.5rem", marginTop: "0.75rem" }}>
          <input
            type="text"
            placeholder="Search name/code/prof"
            value={filters.query}
            onChange={(e) => setFilters((f) => ({ ...f, query: e.target.value }))}
          />
          <div>
            <div style={{ fontSize: 12, marginBottom: 4 }}>Type</div>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                type="button"
                onClick={() => setFilters((f) => ({ ...f, type: f.type === "optional" ? "" : "optional" }))}
                style={{
                  padding: "6px 10px",
                  border: "1px solid #ccc",
                  background: filters.type === "optional" ? "#eee" : "#fff",
                  cursor: "pointer",
                }}
              >
                Optional
              </button>
              <button
                type="button"
                onClick={() => setFilters((f) => ({ ...f, type: f.type === "mandatory" ? "" : "mandatory" }))}
                style={{
                  padding: "6px 10px",
                  border: "1px solid #ccc",
                  background: filters.type === "mandatory" ? "#eee" : "#fff",
                  cursor: "pointer",
                }}
              >
                Mandatory
              </button>
            </div>
          </div>
          <div>
            <div style={{ fontSize: 12, marginBottom: 4 }}>Semester</div>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                type="button"
                onClick={() => setFilters((f) => ({ ...f, semester: f.semester === "winter" ? "" : "winter" }))}
                style={{
                  padding: "6px 10px",
                  border: "1px solid #ccc",
                  background: filters.semester === "winter" ? "#eee" : "#fff",
                  cursor: "pointer",
                }}
              >
                Winter
              </button>
              <button
                type="button"
                onClick={() => setFilters((f) => ({ ...f, semester: f.semester === "summer" ? "" : "summer" }))}
                style={{
                  padding: "6px 10px",
                  border: "1px solid #ccc",
                  background: filters.semester === "summer" ? "#eee" : "#fff",
                  cursor: "pointer",
                }}
              >
                Summer
              </button>
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
            <input
              type="number"
              placeholder="Min credits"
              value={filters.creditsMin}
              onChange={(e) => setFilters((f) => ({ ...f, creditsMin: e.target.value }))}
            />
            <input
              type="number"
              placeholder="Max credits"
              value={filters.creditsMax}
              onChange={(e) => setFilters((f) => ({ ...f, creditsMax: e.target.value }))}
            />
          </div>
          <button
            onClick={() =>
              setFilters({ query: "", type: "", semester: "", creditsMin: "", creditsMax: "" })
            }
          >
            Clear filters
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ margin: 0 }}>Courses</h2>
          {!showFilters && (
            <button onClick={() => setShowFilters(true)}>Show filters</button>
          )}
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", margin: "8px 0", flexWrap: 'wrap' }}>
          {viewMode === 'list' ? (
            <>
              <span style={{ fontSize: 12, color: "#666" }}>Sort by</span>
              <div style={{ display: "flex", gap: 4 }}>
                <button
                  onClick={() => { setSortField("credits"); setSortOrder(sortField === "credits" && sortOrder === "asc" ? "desc" : "asc"); }}
                  style={{ padding: "4px 8px", border: "1px solid #ccc", background: sortField === "credits" ? "#eee" : "#fff" }}
                  title="Toggle credits ascending/descending"
                >
                  Credits {sortField === "credits" ? (sortOrder === "asc" ? "↑" : "↓") : ""}
                </button>
                <button
                  onClick={() => { setSortField("workload"); setSortOrder(sortField === "workload" && sortOrder === "asc" ? "desc" : "asc"); }}
                  style={{ padding: "4px 8px", border: "1px solid #ccc", background: sortField === "workload" ? "#eee" : "#fff" }}
                  title="Toggle workload ascending/descending"
                >
                  Workload {sortField === "workload" ? (sortOrder === "asc" ? "↑" : "↓") : ""}
                </button>
                <button
                  onClick={() => { setSortField(""); setSortOrder("asc"); }}
                  style={{ padding: "4px 8px", border: "1px solid #ccc" }}
                >
                  Clear sort
                </button>
              </div>
            </>
          ) : (
            <>
              <span style={{ fontSize: 12, color: '#666' }}>Pareto sort</span>
              <div style={{ display: 'flex', gap: 6 }}>
                <button
                  onClick={() => setParetoPref(p => ({ ...p, credits: p.credits === 'max' ? 'min' : 'max' }))}
                  style={{ padding: '4px 8px', border: '1px solid #ccc', background: '#fff' }}
                  title="Toggle credits preference (max/min)"
                >
                  Credits {paretoPref.credits === 'max' ? '↓' : '↑'}
                </button>
                <button
                  onClick={() => setParetoPref(p => ({ ...p, workload: p.workload === 'min' ? 'max' : 'min' }))}
                  style={{ padding: '4px 8px', border: '1px solid #ccc', background: '#fff' }}
                  title="Toggle workload preference (min/max)"
                >
                  Workload {paretoPref.workload === 'min' ? '↑' : '↓'}
                </button>
                <button
                  onClick={() => setParetoPref({ credits: 'max', workload: 'min' })}
                  style={{ padding: '4px 8px', border: '1px solid #ccc', background: '#eee' }}
                  title="Reset to default (credits max, workload min)"
                >
                  Default
                </button>
              </div>
            </>
          )}

          <div style={{ marginLeft: 'auto', display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 12, color: '#666', alignSelf: 'center' }}>View</span>
            <button
              onClick={() => setViewMode('list')}
              style={{ padding: '4px 8px', border: '1px solid #ccc', background: viewMode === 'list' ? '#eee' : '#fff' }}
              title="List view"
            >
              List
            </button>
            <button
              onClick={() => setViewMode('grid')}
              style={{ padding: '4px 8px', border: '1px solid #ccc', background: viewMode === 'grid' ? '#eee' : '#fff' }}
              title="Grid view"
            >
              Grid
            </button>
          </div>
        </div>
        <p style={{ marginTop: 4, color: "#555" }}>{courses.length} results</p>

        {viewMode === 'list' ? (
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gridTemplateColumns: '1fr', gap: '12px' }}>
            {courses.map((c) => (
              <li key={c.id ?? c.course_code ?? c.url}>
                <article
                  style={{
                    border: '1px solid #e5e7eb',
                    borderRadius: 8,
                    padding: '12px',
                    boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
                    background: '#fff',
                    display: 'flex',
                    flexDirection: 'column'
                  }}
                >
                  <h3 style={{ margin: 0 }}>
                    {c.url ? (
                      <a href={c.url} target="_blank" rel="noreferrer">{c.course_name}</a>
                    ) : (
                      c.course_name
                    )}
                    {c.course_code && (
                      <small style={{ marginLeft: 8 }}>({c.course_code})</small>
                    )}
                  </h3>
                  <ul style={{ listStyle: 'none', paddingLeft: 0, margin: 0 }}>
                    {c.prof_name && (
                      <li><strong>Professor:</strong> {c.prof_name}</li>
                    )}
                    {Number.isFinite(c.credits) || c.credits ? (
                      <li><strong>Credits:</strong> {c.credits}</li>
                    ) : null}
                    {c.semester && (
                      <li><strong>Semester:</strong> {c.semester}</li>
                    )}
                    {c.exam_form && (
                      <li><strong>Exam:</strong> {c.exam_form}</li>
                    )}
                    {c.workload && (
                      <li><strong>Workload:</strong> {c.workload}</li>
                    )}
                    {c.type && (
                      <li><strong>Type:</strong> {c.type}</li>
                    )}
                  </ul>
                </article>
              </li>
            ))}
          </ul>
        ) : (
          (() => {
            // Build annotated list with metrics
            const annotated = courses.map((c, idx) => ({
              c,
              idx,
              credits: creditsOf(c),
              workload: workloadOf(c),
            }));
            const ranks = computeParetoRanks(annotated, paretoPref);
            const maxRank = ranks.reduce((m, r) => (r !== Infinity && r > m ? r : m), 0);
            const arranged = annotated
              .map((x, i) => ({ ...x, rank: ranks[i] }))
              .sort((a, b) => {
                const ra = a.rank === Infinity ? Number.MAX_SAFE_INTEGER : a.rank;
                const rb = b.rank === Infinity ? Number.MAX_SAFE_INTEGER : b.rank;
                if (ra !== rb) return ra - rb; // lower rank first
                // within same rank: order by current preferences
                if (a.credits !== b.credits) {
                  return paretoPref.credits === 'max' ? (b.credits - a.credits) : (a.credits - b.credits);
                }
                if (a.workload !== b.workload) {
                  return paretoPref.workload === 'min' ? (a.workload - b.workload) : (b.workload - a.workload);
                }
                return 0;
              });

            return (
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: `repeat(auto-fill, minmax(${GRID_MIN_WIDTH}px, 1fr))`,
                  gap: '12px'
                }}
              >
                {arranged.map(({ c, rank }) => {
                  const t = maxRank <= 0 || rank === Infinity ? 1 : rank / maxRank; // 0..1, worst close to 1
                  const minL = 25, maxL = 90;
                  const lightness = Math.round(minL + t * (maxL - minL));
                  const bg = colorForRank(rank === Infinity ? maxRank : rank, maxRank);
                  const fg = textColorForBgHslLightness(lightness);
                  return (
                    <article
                      key={c.id ?? c.course_code ?? c.url}
                      style={{
                        border: '1px solid rgba(0,0,0,0.08)',
                        borderRadius: 8,
                        padding: '12px',
                        boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
                        background: bg,
                        color: fg,
                        display: 'flex',
                        flexDirection: 'column',
                        minHeight: 120
                      }}
                    >
                      <h3 style={{ margin: 0, fontSize: 16, lineHeight: '20px' }}>
                        {c.url ? (
                          <a href={c.url} target="_blank" rel="noreferrer" style={{ color: 'inherit' }}>{c.course_name}</a>
                        ) : (
                          c.course_name
                        )}
                      </h3>
                      {c.course_code && (
                        <div style={{ fontSize: 12, opacity: 0.85, marginTop: 2 }}>{c.course_code}</div>
                      )}
                      <div style={{ marginTop: 8, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, fontSize: 12 }}>
                        {Number.isFinite(c.credits) || c.credits ? (
                          <div><strong>ECTS:</strong> {c.credits}</div>
                        ) : <div />}
                        {c.semester && (
                          <div><strong>Sem:</strong> {c.semester}</div>
                        )}
                        {c.workload && (
                          <div><strong>Work:</strong> {c.workload}</div>
                        )}
                        {c.type && (
                          <div><strong>Type:</strong> {c.type}</div>
                        )}
                      </div>
                    </article>
                  );
                })}
              </div>
            );
          })()
        )}

        <div style={{ marginTop: "1rem" }}>
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            style={{ marginRight: "1rem" }}
          >
            Previous
          </button>
          <span>Page {page}</span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={courses.length < pageSize}
            style={{ marginLeft: "1rem" }}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}

export default CoursesList;
