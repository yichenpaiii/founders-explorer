import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { getCourses } from "../api/courses_api";  // adjust path if needed

const GRID_MIN_WIDTH = 220; // px

const SCORE_FIELDS = [
  { key: 'max_score_skills_sigmoid', label: 'Skills' },
  { key: 'max_score_product_sigmoid', label: 'Product' },
  { key: 'max_score_venture_sigmoid', label: 'Venture' },
  { key: 'max_score_foundations_sigmoid', label: 'Foundations' },
];

const MIN_SCORE_SLIDERS = [
  { key: 'minSkills', label: 'Skills' },
  { key: 'minProduct', label: 'Product' },
  { key: 'minVenture', label: 'Venture' },
  { key: 'minFoundations', label: 'Foundations' },
];

const TAG_COLORS = [
  '#2563eb', '#059669', '#f97316', '#a855f7', '#ec4899',
  '#14b8a6', '#facc15', '#ef4444', '#6366f1', '#10b981',
];

function colorForTag(tag) {
  if (!tag) return '#4b5563';
  let hash = 0;
  for (let i = 0; i < tag.length; i += 1) {
    hash = (hash << 5) - hash + tag.charCodeAt(i);
    hash |= 0;
  }
  const index = Math.abs(hash) % TAG_COLORS.length;
  return TAG_COLORS[index];
}

function tagTextColor(hex) {
  const normalized = hex.replace('#', '');
  const bigint = parseInt(normalized, 16);
  const r = (bigint >> 16) & 255;
  const g = (bigint >> 8) & 255;
  const b = bigint & 255;
  const luminance = 0.299 * r + 0.587 * g + 0.114 * b;
  return luminance > 170 ? '#111' : '#fff';
}

function renderLevelTags(levels) {
  if (!Array.isArray(levels) || levels.length === 0) return null;
  const uniqueLevels = Array.from(new Set(levels.map((name) => name?.trim()).filter(Boolean)));
  if (uniqueLevels.length === 0) return null;
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 4 }}>
      {uniqueLevels.map((name) => {
        const color = colorForTag(name);
        return (
          <span
            key={name}
            style={{
              background: color,
              color: tagTextColor(color),
              padding: '2px 8px',
              borderRadius: 999,
              fontSize: 10,
              fontWeight: 600,
              opacity: 0.85,
            }}
          >
            {name}
          </span>
        );
      })}
    </div>
  );
}

function renderProgramTags(programs) {
  if (!Array.isArray(programs) || programs.length === 0) return null;
  const uniquePrograms = Array.from(new Set(programs.map((name) => name?.trim()).filter(Boolean)));
  if (uniquePrograms.length === 0) return null;
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 4 }}>
      {uniquePrograms.map((name) => {
        const color = colorForTag(name);
        return (
          <span
            key={name}
            style={{
              background: color,
              color: tagTextColor(color),
              padding: '2px 8px',
              borderRadius: 999,
              fontSize: 11,
              fontWeight: 600,
            }}
          >
            {name}
          </span>
        );
      })}
    </div>
  );
}

const createDefaultFilters = () => ({
  query: "",
  type: "",
  semester: "",
  creditsMin: "",
  creditsMax: "",
  minSkills: 0,
  minProduct: 0,
  minVenture: 0,
  minFoundations: 0,
  degree: "",
  level: "",
  major: "",
  minor: "",
});

const FILTER_KEYS = Object.keys(createDefaultFilters());

function parseFiltersFromSearch(search) {
  const base = createDefaultFilters();
  if (!search) return base;
  const sp = new URLSearchParams(search);
  base.degree = sp.get('degree') || '';
  base.level = sp.get('level') || '';
  base.major = sp.get('major') || '';
  base.type = sp.get('type') || '';
  base.semester = sp.get('semester') || '';
  base.minor = sp.get('minor') || '';
  if (base.level && !base.semester) {
    base.semester = inferSemesterFromLevel(base.level) || '';
  }
  const creditsMinParam = sp.get('creditsMin');
  if (creditsMinParam !== null) base.creditsMin = creditsMinParam;
  const creditsMaxParam = sp.get('creditsMax');
  if (creditsMaxParam !== null) base.creditsMax = creditsMaxParam;

  const parseScore = (value) => {
    if (value === null) return undefined;
    const num = Number(value);
    return Number.isFinite(num) ? num : undefined;
  };

  const minSkillsParam = parseScore(sp.get('minSkills'));
  if (minSkillsParam !== undefined) base.minSkills = minSkillsParam;
  const minProductParam = parseScore(sp.get('minProduct'));
  if (minProductParam !== undefined) base.minProduct = minProductParam;
  const minVentureParam = parseScore(sp.get('minVenture'));
  if (minVentureParam !== undefined) base.minVenture = minVentureParam;
  const minFoundationsParam = parseScore(sp.get('minFoundations'));
  if (minFoundationsParam !== undefined) base.minFoundations = minFoundationsParam;
  return base;
}

function filtersAreEqual(a, b) {
  if (a === b) return true;
  if (!a || !b) return false;
  for (const key of FILTER_KEYS) {
    const va = a[key];
    const vb = b[key];
    if (Number.isFinite(va) || Number.isFinite(vb)) {
      if (Number(va) !== Number(vb)) return false;
    } else if ((va ?? '') !== (vb ?? '')) {
      return false;
    }
  }
  return true;
}

function getDegreeOptions(tree) {
  if (!tree || typeof tree !== 'object') return [];
  return Object.keys(tree);
}

function getLevelOptions(tree, degree) {
  if (!tree || !degree || !tree[degree]) return [];
  return Object.keys(tree[degree] || {})
    .filter((lvl) => /^[A-Za-z]+\d+$/i.test(lvl))
    .sort();
}

function getMajorOptions(tree, degree, level) {
  if (!tree || !degree || !level) return [];
  if (degree === 'PhD') {
    const list = Array.isArray(tree.PhD?.edoc) ? tree.PhD.edoc : [];
    return list.slice().sort();
  }
  const bucket = tree[degree];
  const list = Array.isArray(bucket?.[level]) ? bucket[level] : [];
  return list.slice().sort();
}

function withValueOption(options, value) {
  if (!value) return options;
  if (options.includes(value)) return options;
  return [...options, value];
}

function getMinorOptions(tree, degree, level) {
  if (!tree || degree !== 'MA') return [];
  const source = tree.MA || {};
  const autumn = Array.isArray(source['Minor Autumn Semester']) ? source['Minor Autumn Semester'] : [];
  const spring = Array.isArray(source['Minor Spring Semester']) ? source['Minor Spring Semester'] : [];
  if (!level) {
    return Array.from(new Set([...autumn, ...spring])).sort();
  }
  const match = level.match(/^MA(\d+)/i);
  if (match) {
    const idx = Number(match[1]);
    if (Number.isFinite(idx)) {
      return (idx % 2 === 1 ? autumn : spring).slice().sort();
    }
  }
  if (level.toLowerCase().includes('autumn')) return autumn.slice().sort();
  if (level.toLowerCase().includes('spring')) return spring.slice().sort();
  return Array.from(new Set([...autumn, ...spring])).sort();
}

function inferSemesterFromLevel(level) {
  if (!level) return '';
  const lower = level.toLowerCase();
  if (lower.includes('spring')) return 'summer';
  if (lower.includes('autumn')) return 'winter';
  const match = level.match(/(\d+)/);
  if (match) {
    const num = Number(match[1]);
    if (Number.isFinite(num)) {
      return num % 2 === 0 ? 'summer' : 'winter';
    }
  }
  return '';
}

function adjustLevelForSemester(level, degree, semester) {
  if (!level || !semester) return level;
  const match = level.match(/^([A-Za-z]+)(\d+)$/);
  if (match) {
    const prefix = match[1];
    let num = Number(match[2]);
    if (Number.isFinite(num)) {
      if (semester === 'winter' && num % 2 === 0) {
        num = Math.max(1, num - 1);
      } else if (semester === 'summer' && num % 2 === 1) {
        num = num + 1;
      }
      return `${prefix}${num}`;
    }
  }
  if (degree === 'MA' && level.toLowerCase().includes('minor')) {
    if (semester === 'winter' && level.toLowerCase().includes('spring')) {
      return level.replace(/Spring/i, 'Autumn');
    }
    if (semester === 'summer' && level.toLowerCase().includes('autumn')) {
      return level.replace(/Autumn/i, 'Spring');
    }
  }
  return level;
}

function normalizeScore(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return null;
  if (num < 0) return 0;
  if (num > 1) return 1;
  return num;
}

function ScoreSummary({ course, theme = 'light' }) {
  const entries = SCORE_FIELDS.map(({ key, label }) => {
    const value = normalizeScore(course?.[key]);
    return { label, value };
  });

  const isDark = theme === 'dark';
  const trackColor = isDark ? 'rgba(255,255,255,0.25)' : '#e5e7eb';
  const fillColor = isDark ? 'rgba(255,255,255,0.85)' : '#2563eb';
  const labelColor = isDark ? 'rgba(255,255,255,0.8)' : '#374151';

  return (
    <div
      style={{
        marginTop: 10,
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))',
        gap: 8,
      }}
    >
      {entries.map(({ label, value }) => (
        <div key={label} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: 11, color: labelColor }}>{label}</span>
          <div
            style={{
              height: 6,
              borderRadius: 9999,
              background: trackColor,
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                width: value != null ? `${Math.round(value * 100)}%` : '0%',
                height: '100%',
                background: fillColor,
                transition: 'width 0.2s ease',
              }}
            />
          </div>
          <span style={{ fontSize: 12, fontWeight: 600 }}>
            {value != null ? value.toFixed(2) : '–'}
          </span>
        </div>
      ))}
    </div>
  );
}

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
  const navigate = useNavigate();
  const [courses, setCourses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(30);
  const [totalResults, setTotalResults] = useState(0);
  const [showFilters, setShowFilters] = useState(true);
  const [programsTree, setProgramsTree] = useState(null);
  const [appliedFilters, setAppliedFilters] = useState(() => parseFiltersFromSearch(location.search));
  const [draftFilters, setDraftFilters] = useState(() => parseFiltersFromSearch(location.search));
  const [sortField, setSortField] = useState("");
  const [sortOrder, setSortOrder] = useState("asc");
  const [viewMode, setViewMode] = useState("list"); // 'list' | 'grid'
  const [paretoPref, setParetoPref] = useState({ credits: 'max', workload: 'min' }); // 'max'|'min' for each

  useEffect(() => {
    let cancelled = false;
    async function loadProgramsTree() {
      try {
        const response = await fetch('/programs_tree.json', { cache: 'no-store' });
        if (!response.ok) {
          throw new Error(`Failed to fetch programs_tree.json: ${response.status}`);
        }
        const contentType = response.headers.get('content-type') || '';
        if (!contentType.includes('application/json')) {
          const snippet = await response.text();
          throw new Error(`Unexpected content-type: ${contentType}. Body starts with: ${snippet.slice(0, 60)}`);
        }
        const json = await response.json();
        if (!cancelled) {
          setProgramsTree(json);
        }
      } catch (err) {
        if (!cancelled) {
          setProgramsTree(null);
          console.warn('Failed to load programs_tree.json', err);
        }
      }
    }
    loadProgramsTree();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const inferred = inferSemesterFromLevel(appliedFilters.level);
    const fallback = appliedFilters.semester || '';
    const finalSemester = inferred || fallback;
    if (finalSemester && finalSemester !== appliedFilters.semester) {
      setAppliedFilters((prev) => ({ ...prev, semester: finalSemester }));
      setDraftFilters((prev) => ({ ...prev, semester: finalSemester }));
    }
  }, [appliedFilters.level]);

useEffect(() => {
    const parsed = parseFiltersFromSearch(location.search);
    setAppliedFilters((prev) => (filtersAreEqual(prev, parsed) ? prev : parsed));
  }, [location.search]);

  useEffect(() => {
    setDraftFilters(appliedFilters);
  }, [appliedFilters]);

  useEffect(() => {
    const params = new URLSearchParams();

    if (appliedFilters.degree) params.set('degree', appliedFilters.degree);
    if (appliedFilters.level) params.set('level', appliedFilters.level);
    if (appliedFilters.major) params.set('major', appliedFilters.major);
    if (appliedFilters.minor) params.set('minor', appliedFilters.minor);
    if (appliedFilters.type) params.set('type', appliedFilters.type);
    if (appliedFilters.semester) params.set('semester', appliedFilters.semester);
    if (appliedFilters.creditsMin !== '') params.set('creditsMin', appliedFilters.creditsMin);
    if (appliedFilters.creditsMax !== '') params.set('creditsMax', appliedFilters.creditsMax);
    const setScoreParam = (key, value) => {
      if (Number(value) > 0) params.set(key, String(value));
    };
    setScoreParam('minSkills', appliedFilters.minSkills);
    setScoreParam('minProduct', appliedFilters.minProduct);
    setScoreParam('minVenture', appliedFilters.minVenture);
    setScoreParam('minFoundations', appliedFilters.minFoundations);

    const nextSearch = params.toString();
    const next = nextSearch ? `?${nextSearch}` : '';
    if (location.search !== next) {
      navigate({ pathname: location.pathname, search: next }, { replace: true });
    }
  }, [appliedFilters, location.pathname, location.search, navigate]);

  const filtersDirty = useMemo(
    () => draftFilters.query !== appliedFilters.query,
    [draftFilters.query, appliedFilters.query],
  );

  const degreeOptions = useMemo(
    () => withValueOption(getDegreeOptions(programsTree), draftFilters.degree),
    [programsTree, draftFilters.degree],
  );

  const levelOptions = useMemo(
    () => withValueOption(getLevelOptions(programsTree, draftFilters.degree), draftFilters.level),
    [programsTree, draftFilters.degree, draftFilters.level],
  );

  const majorOptions = useMemo(
    () => withValueOption(getMajorOptions(programsTree, draftFilters.degree, draftFilters.level), draftFilters.major),
    [programsTree, draftFilters.degree, draftFilters.level, draftFilters.major],
  );

  const minorOptions = useMemo(
    () => withValueOption(getMinorOptions(programsTree, draftFilters.degree, draftFilters.level), draftFilters.minor),
    [programsTree, draftFilters.degree, draftFilters.level, draftFilters.minor],
  );

  const levelDisabled = !draftFilters.degree || levelOptions.length === 0;
  const majorDisabled = !draftFilters.degree || !draftFilters.level || majorOptions.length === 0;
  const minorDisabled = draftFilters.degree !== 'MA' || !draftFilters.level || minorOptions.length === 0;

  const handleApplyFilters = () => {
    setPage(1);
    setAppliedFilters((prev) => ({ ...prev, query: draftFilters.query }));
  };

  const handleClearFilters = () => {
    const reset = createDefaultFilters();
    setDraftFilters(reset);
    setAppliedFilters(reset);
    setPage(1);
  };

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      setError(null);
      try {
        const params = {
          page,
          pageSize,
          // map UI filters to backend query params
          q: appliedFilters.query || undefined,
          type: appliedFilters.type || undefined,
          semester: appliedFilters.semester || undefined,
          degree: appliedFilters.degree || undefined,
          creditsMin: appliedFilters.creditsMin !== "" ? Number(appliedFilters.creditsMin) : undefined,
          creditsMax: appliedFilters.creditsMax !== "" ? Number(appliedFilters.creditsMax) : undefined,
          level: appliedFilters.level || undefined,
          major: appliedFilters.major || undefined,
          minor: appliedFilters.minor || undefined,
          sortField: sortField || undefined,
          sortOrder: sortField ? sortOrder : undefined,
          minSkills: appliedFilters.minSkills > 0 ? appliedFilters.minSkills : undefined,
          minProduct: appliedFilters.minProduct > 0 ? appliedFilters.minProduct : undefined,
          minVenture: appliedFilters.minVenture > 0 ? appliedFilters.minVenture : undefined,
          minFoundations: appliedFilters.minFoundations > 0 ? appliedFilters.minFoundations : undefined,
        };
        const data = await getCourses(params);
        console.log("API response:", data);
        setCourses(data.items || []);
        setTotalResults(Number(data.total || 0));
        if (!data.items || data.items.length === 0) {
          console.debug('No course results returned for current filters');
        }
      } catch (err) {
        setError(err?.message || "Failed to load courses");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [page, pageSize, appliedFilters, sortField, sortOrder]);

  useEffect(() => {
    setPage(1);
  }, [appliedFilters, sortField, sortOrder]);

  return (
    <div style={{ display: "flex", gap: "1rem" }}>
      {/* Left Filter Bar */}
      <aside
        style={{
          width: showFilters ? 'clamp(220px, 26vw, 320px)' : 0,
          flex: showFilters ? '0 0 clamp(220px, 26vw, 320px)' : '0 0 0',
          boxSizing: 'border-box',
          transition: "width 0.2s ease",
          position: "sticky",
          top: 0,
          height: "100vh",
          alignSelf: "flex-start",
          overflowY: showFilters ? "auto" : "hidden",
          overflowX: "hidden",
          borderRight: "1px solid #eee",
          paddingRight: showFilters ? "1rem" : 0,
          marginRight: showFilters ? "1rem" : 0,
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
            value={draftFilters.query}
            onChange={(e) => setDraftFilters((f) => ({ ...f, query: e.target.value }))}
          />
          <button
            type="button"
            onClick={handleApplyFilters}
            disabled={!filtersDirty}
            style={{
              padding: "8px 12px",
              border: "1px solid #ccc",
              background: filtersDirty ? "#2563eb" : "#e5e7eb",
              color: filtersDirty ? "#fff" : "#6b7280",
              cursor: filtersDirty ? "pointer" : "not-allowed",
            }}
          >
            Search
          </button>
          <div>
            <div style={{ fontSize: 12, marginBottom: 4 }}>Degree</div>
            <select
              value={draftFilters.degree}
              onChange={(e) => {
                const nextDegree = e.target.value;
                setDraftFilters((prev) => ({
                  ...prev,
                  degree: nextDegree,
                  level: '',
                  major: '',
                  minor: '',
                }));
                setAppliedFilters((prev) => ({
                  ...prev,
                  degree: nextDegree,
                  level: '',
                  major: '',
                  minor: '',
                }));
              }}
              style={{ width: '100%', padding: '6px 8px', border: '1px solid #ccc', borderRadius: 4 }}
            >
              <option value="">Any degree</option>
              {degreeOptions.map((opt) => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          </div>
          <div>
            <div style={{ fontSize: 12, marginBottom: 4 }}>Level</div>
            <select
              value={draftFilters.level}
              onChange={(e) => {
                const nextLevel = e.target.value;
                const inferredSemester = inferSemesterFromLevel(nextLevel);
                setDraftFilters((prev) => ({
                  ...prev,
                  level: nextLevel,
                  major: '',
                  minor: '',
                  semester: inferredSemester || prev.semester,
                }));
                setAppliedFilters((prev) => ({
                  ...prev,
                  level: nextLevel,
                  major: '',
                  minor: '',
                  semester: inferredSemester || prev.semester,
                }));
              }}
              disabled={levelDisabled}
              style={{
                width: '100%',
                padding: '6px 8px',
                border: '1px solid #ccc',
                borderRadius: 4,
                background: levelDisabled ? '#f3f4f6' : '#fff',
                color: levelDisabled ? '#9ca3af' : '#111',
              }}
            >
              <option value="">Any level</option>
              {levelOptions.map((opt) => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          </div>
          <div>
            <div style={{ fontSize: 12, marginBottom: 4 }}>Major</div>
            <select
              value={draftFilters.major}
              onChange={(e) => {
                const nextMajor = e.target.value;
                setDraftFilters((prev) => ({
                  ...prev,
                  major: nextMajor,
                }));
                setAppliedFilters((prev) => ({
                  ...prev,
                  major: nextMajor,
                }));
              }}
              disabled={majorDisabled}
              style={{
                width: '100%',
                padding: '6px 8px',
                border: '1px solid #ccc',
                borderRadius: 4,
                background: majorDisabled ? '#f3f4f6' : '#fff',
                color: majorDisabled ? '#9ca3af' : '#111',
              }}
            >
              <option value="">Any major</option>
              {majorOptions.map((opt) => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          </div>
          {draftFilters.degree === 'MA' && (
            <div>
              <div style={{ fontSize: 12, marginBottom: 4 }}>Minor</div>
              <select
                value={draftFilters.minor}
                onChange={(e) => {
                  const nextMinor = e.target.value;
                  setDraftFilters((prev) => ({
                    ...prev,
                    minor: nextMinor,
                  }));
                  setAppliedFilters((prev) => ({
                    ...prev,
                    minor: nextMinor,
                  }));
                }}
                disabled={minorDisabled}
                style={{
                  width: '100%',
                  padding: '6px 8px',
                  border: '1px solid #ccc',
                  borderRadius: 4,
                  background: minorDisabled ? '#f3f4f6' : '#fff',
                  color: minorDisabled ? '#9ca3af' : '#111',
                }}
              >
                <option value="">No minor preference</option>
                {minorOptions.map((opt) => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            </div>
          )}
          <div>
            <div style={{ fontSize: 12, marginBottom: 4 }}>Type</div>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                type="button"
                onClick={() => {
                  setDraftFilters((prev) => {
                    const nextType = prev.type === "optional" ? "" : "optional";
                    const next = { ...prev, type: nextType };
                    setAppliedFilters((applied) => ({ ...applied, type: nextType }));
                    return next;
                  });
                }}
                style={{
                  padding: "6px 10px",
                  border: "1px solid #ccc",
                  background: draftFilters.type === "optional" ? "#eee" : "#fff",
                  cursor: "pointer",
                }}
              >
                Optional
              </button>
              <button
                type="button"
                onClick={() => {
                  setDraftFilters((prev) => {
                    const nextType = prev.type === "mandatory" ? "" : "mandatory";
                    const next = { ...prev, type: nextType };
                    setAppliedFilters((applied) => ({ ...applied, type: nextType }));
                    return next;
                  });
                }}
                style={{
                  padding: "6px 10px",
                  border: "1px solid #ccc",
                  background: draftFilters.type === "mandatory" ? "#eee" : "#fff",
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
                onClick={() => {
                  setDraftFilters((prev) => {
                    const nextSemester = prev.semester === "winter" ? "" : "winter";
                    let nextLevel = prev.level;
                    if (nextSemester) {
                      nextLevel = adjustLevelForSemester(prev.level, prev.degree, nextSemester);
                    }
                    const next = { ...prev, semester: nextSemester, level: nextLevel };
                    setAppliedFilters((applied) => ({ ...applied, semester: nextSemester, level: nextLevel }));
                    return next;
                  });
                }}
                style={{
                  padding: "6px 10px",
                  border: "1px solid #ccc",
                  background: draftFilters.semester === "winter" ? "#eee" : "#fff",
                  cursor: "pointer",
                }}
              >
                Winter
              </button>
              <button
                type="button"
                onClick={() => {
                  setDraftFilters((prev) => {
                    const nextSemester = prev.semester === "summer" ? "" : "summer";
                    let nextLevel = prev.level;
                    if (nextSemester) {
                      nextLevel = adjustLevelForSemester(prev.level, prev.degree, nextSemester);
                    }
                    const next = { ...prev, semester: nextSemester, level: nextLevel };
                    setAppliedFilters((applied) => ({ ...applied, semester: nextSemester, level: nextLevel }));
                    return next;
                  });
                }}
                style={{
                  padding: "6px 10px",
                  border: "1px solid #ccc",
                  background: draftFilters.semester === "summer" ? "#eee" : "#fff",
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
              value={draftFilters.creditsMin}
              onChange={(e) => {
                const { value } = e.target;
                setDraftFilters((prev) => ({ ...prev, creditsMin: value }));
                setAppliedFilters((prev) => ({ ...prev, creditsMin: value }));
              }}
            />
            <input
              type="number"
              placeholder="Max credits"
              value={draftFilters.creditsMax}
              onChange={(e) => {
                const { value } = e.target;
                setDraftFilters((prev) => ({ ...prev, creditsMax: value }));
                setAppliedFilters((prev) => ({ ...prev, creditsMax: value }));
              }}
            />
          </div>
          <div style={{ display: 'grid', gap: 10 }}>
            {MIN_SCORE_SLIDERS.map(({ key, label }) => (
              <div key={key} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                  <span>{label} minimum</span>
                  <span style={{ color: '#555' }}>≥ {draftFilters[key].toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.01"
                  value={draftFilters[key]}
                  onChange={(e) => {
                    const value = Number(e.target.value);
                    setDraftFilters((prev) => ({ ...prev, [key]: value }));
                    setAppliedFilters((prev) => ({ ...prev, [key]: value }));
                  }}
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#888' }}>
                  <span>0</span>
                  <span>1</span>
                </div>
              </div>
            ))}
          </div>
          <button
            type="button"
            onClick={handleClearFilters}
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
        {error && (
          <div style={{ margin: '8px 0', padding: '8px 12px', background: '#fee2e2', border: '1px solid #fca5a5', borderRadius: 6, color: '#991b1b' }}>
            {error}
          </div>
        )}
        {loading && (
          <div style={{ margin: '8px 0', fontSize: 12, color: '#4b5563' }}>Loading courses…</div>
        )}
        <div style={{ display: "flex", gap: 8, alignItems: "center", margin: "8px 0", flexWrap: 'wrap' }}>
          {viewMode === 'list' ? (
            <>
              <span style={{ fontSize: 12, color: "#666" }}>Sort by</span>
              <div style={{ display: "flex", gap: 4, flexWrap: 'wrap' }}>
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
                {[
                  { key: 'score_skills', label: 'Skills score' },
                  { key: 'score_product', label: 'Product score' },
                  { key: 'score_venture', label: 'Venture score' },
                  { key: 'score_foundations', label: 'Foundations score' },
                ].map(({ key, label }) => (
                  <button
                    key={key}
                    onClick={() => {
                      setSortField(key);
                      setSortOrder(sortField === key ? (sortOrder === "desc" ? "asc" : "desc") : "desc");
                    }}
                    style={{ padding: "4px 8px", border: "1px solid #ccc", background: sortField === key ? "#eee" : "#fff" }}
                    title={`Toggle ${label} ascending/descending`}
                  >
                    {label} {sortField === key ? (sortOrder === "asc" ? "↑" : "↓") : ""}
                  </button>
                ))}
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
        {(() => {
          const totalPages = Math.max(1, Math.ceil(totalResults / pageSize));
          const shown = courses.length;
          return (
            <p style={{ marginTop: 4, color: "#555" }}>
              Showing {shown} of {totalResults} results · Page {page} / {totalPages}
            </p>
          );
        })()}

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
                  {renderProgramTags(c.available_programs)}
                  {renderLevelTags(c.available_levels)}
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
                  <ScoreSummary course={c} />
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
                      {renderProgramTags(c.available_programs)}
                      {renderLevelTags(c.available_levels)}
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
                      <ScoreSummary course={c} theme={fg === '#fff' ? 'dark' : 'light'} />
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
          {(() => {
            const totalPages = Math.max(1, Math.ceil(totalResults / pageSize));
            return (
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={page >= totalPages}
                style={{ marginLeft: "1rem" }}
              >
                Next
              </button>
            );
          })()}
        </div>
      </div>
    </div>
  );
}

export default CoursesList;
