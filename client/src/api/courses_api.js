export async function getCourses() {
  try {
    const res = await fetch("http://localhost:3000/api/courses");

    // Check status before attempting to read the body
    if (!res.ok) {
      // Try to capture any error text without consuming JSON twice
      const errorText = await res.text().catch(() => "");
      throw new Error(
        `HTTP ${res.status} ${res.statusText}${errorText ? ` - ${errorText}` : ""}`
      );
    }

    const data = await res.json();
    console.log("Fetched courses:", data);
    return data;
  } catch (err) {
    console.error("Failed to fetch courses:", err);
    throw err;
  }
}