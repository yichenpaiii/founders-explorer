export async function getCourses({
  page,
  pageSize,
  q,
  type,
  semester,
  creditsMin,
  creditsMax,
  availablePrograms,
  sortField,
  sortOrder,
  minSkills,
  minProduct,
  minVenture,
  minFoundations,
} = {}) {
  try {
    const url = new URL("/api/courses", "http://localhost:3000");

    // Append query params if provided
    if (page != null) url.searchParams.set("page", String(page));
    if (pageSize != null) url.searchParams.set("pageSize", String(pageSize));
    if (q) url.searchParams.set("q", q);
    if (type) url.searchParams.set("type", type);
    if (semester) url.searchParams.set("semester", semester);
    if (creditsMin != null) url.searchParams.set("creditsMin", String(creditsMin));
    if (creditsMax != null) url.searchParams.set("creditsMax", String(creditsMax));
    if (availablePrograms && Array.isArray(availablePrograms)) {
      const csv = availablePrograms.join(',');
      if (csv) url.searchParams.set('available_programs', csv);
    } else if (typeof availablePrograms === 'string' && availablePrograms.trim()) {
      url.searchParams.set('available_programs', availablePrograms.trim());
    }
    if (sortField) url.searchParams.set('sortField', sortField);
    if (sortOrder) url.searchParams.set('sortOrder', sortOrder);

    const scoreParams = {
      minSkills,
      minProduct,
      minVenture,
      minFoundations,
    };

    for (const [key, value] of Object.entries(scoreParams)) {
      if (value != null && !Number.isNaN(value)) {
        url.searchParams.set(key, String(value));
      }
    }

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
