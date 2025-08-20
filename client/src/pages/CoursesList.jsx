import { useEffect, useState } from "react";
import { getCourses } from "../api/courses_api";  // adjust path if needed

function CoursesList() {
  const [courses, setCourses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function fetchData() {
      try {
        const data = await getCourses(); // expects backend to return JSON list
        console.log("API response:", data);
        setCourses(data.items || []);
      } catch (err) {
        setError("Failed to load courses");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  if (loading) return <p>Loading courses...</p>;
  if (error) return <p>{error}</p>;

  return (
    <div>
      <h2>Courses</h2>
      <ul>
        {courses.map(course => (
          <li key={course.id}>
            <strong>{course.title}</strong>
            <br />
            <span>{course.description}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default CoursesList;