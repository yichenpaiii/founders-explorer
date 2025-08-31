import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { getCourses } from "../api/courses_api";  // adjust path if needed

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
        <div style={{ display: "flex", gap: 8, alignItems: "center", margin: "8px 0" }}>
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
        </div>
        <p style={{ marginTop: 4, color: "#555" }}>{courses.length} results</p>

        <ul>
          {courses.map((c) => (
            <li key={c.id ?? c.course_code ?? c.url} style={{ marginBottom: "1rem" }}>
              <article>
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
                <ul style={{ listStyle: "none", paddingLeft: 0, margin: 0 }}>
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
