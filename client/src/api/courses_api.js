export async function getCourses({ page, pageSize, search } = {}) {
  try {
    const url = new URL("/api/courses", "http://localhost:3000");

    // Append query params if provided
    if (page != null) url.searchParams.set("page", String(page));
    if (pageSize != null) url.searchParams.set("pageSize", String(pageSize));
    if (search) url.searchParams.set("q", search);

    const res = await fetch(url.toString());

    if (!res.ok) {
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