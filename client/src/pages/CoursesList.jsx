import { useEffect, useState } from "react";
import { getCourses } from "../api/courses_api";  // adjust path if needed

function CoursesList() {
  const [courses, setCourses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      try {
        const data = await getCourses({ page, pageSize }); // expects backend to return JSON list
        console.log("API response:", data);
        setCourses(data.items || []);
      } catch (err) {
        setError("Failed to load courses");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [page, pageSize]);

  if (loading) return <p>Loading courses...</p>;
  if (error) return <p>{error}</p>;

  return (
    <div>
      <h2>Courses</h2>
      <ul>
        {courses.map((c) => (
          <li key={c.id ?? c.course_code ?? c.url} style={{ marginBottom: '1rem' }}>
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
      <div style={{ marginTop: '1rem' }}>
        <button
          onClick={() => setPage((p) => Math.max(1, p - 1))}
          disabled={page === 1}
          style={{ marginRight: '1rem' }}
        >
          Previous
        </button>
        <span>Page {page}</span>
        <button
          onClick={() => setPage((p) => p + 1)}
          disabled={courses.length < pageSize}
          style={{ marginLeft: '1rem' }}
        >
          Next
        </button>
      </div>
    </div>
  );
}

export default CoursesList;