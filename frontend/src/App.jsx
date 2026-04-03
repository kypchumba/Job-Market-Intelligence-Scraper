import { useEffect, useMemo, useState } from "react";

import { exportCsv, getJobs, getStats, runScrape } from "./api";

const initialFilters = {
  keyword: "",
  location: "",
  source: "",
  job_type: "",
};

const MAX_DETAIL_ROWS = 20;

export default function App() {
  const [filters, setFilters] = useState(initialFilters);
  const [jobs, setJobs] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [scraping, setScraping] = useState(false);
  const [error, setError] = useState("");
  const [lastRun, setLastRun] = useState("");
  const [expandedJobId, setExpandedJobId] = useState("");

  async function loadDashboard(activeFilters = filters) {
    setLoading(true);
    setError("");
    try {
      const [jobsResponse, statsResponse] = await Promise.all([
        getJobs(activeFilters),
        getStats(),
      ]);
      setJobs(jobsResponse.items);
      setStats(statsResponse);
    } catch (err) {
      setError(err.message || "Unable to load dashboard data.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDashboard();
  }, []);

  const sourceOptions = useMemo(
    () => [
      "remoteok",
      "weworkremotely",
      "greenhouse",
      "lever",
      "ashby",
      "careerspage",
      "myjobmag",
      "brightermonday",
      "corporatestaffing",
      "fuzu",
    ],
    []
  );
  const topSource = stats?.sources?.[0]?.source || "n/a";

  async function handleScrape() {
    setScraping(true);
    setError("");
    try {
      const response = await runScrape();
      setLastRun(
        `${response.total_inserted} new jobs added at ${new Date(response.finished_at).toLocaleString()}`
      );
      await loadDashboard(filters);
    } catch (err) {
      setError(err.message || "Scrape request failed.");
    } finally {
      setScraping(false);
    }
  }

  function handleFilterChange(event) {
    const { name, value } = event.target;
    setFilters((current) => ({ ...current, [name]: value }));
  }

  async function handleApplyFilters(event) {
    event.preventDefault();
    await loadDashboard(filters);
  }

  function handleToggleDetails(jobId) {
    setExpandedJobId((current) => (current === jobId ? "" : jobId));
  }

  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Distributed Job Intelligence Platform</p>
          <h1>Track global hiring signals through one real-time dashboard.</h1>
          <p className="hero-copy">
            Aggregate remote-first and enterprise job feeds, filter opportunity streams and
            monitor talent demand from a single operational view.
          </p>
        </div>
        <div className="hero-actions">
          <button className="primary-button" onClick={handleScrape} disabled={scraping}>
            {scraping ? "Scraping..." : "Run Scrape"}
          </button>
          <a className="secondary-button" href={exportCsv()}>
            Export CSV
          </a>
        </div>
      </header>

      {error ? <section className="banner error">{error}</section> : null}
      {lastRun ? <section className="banner success">{lastRun}</section> : null}

      <section className="stats-grid">
        <StatCard label="Tracked Jobs" value={stats?.total_jobs ?? "--"} accent="sun" />
        <StatCard label="Remote Roles" value={stats?.remote_jobs ?? "--"} accent="sky" />
        <StatCard label="Top Source" value={topSource} accent="mint" />
        <StatCard
          label="Hot Skill"
          value={stats?.top_skills?.[0]?.label || "awaiting data"}
          accent="coral"
        />
      </section>

      <section className="panel">
        <div className="panel-head">
          <div>
            <p className="section-kicker">Search and filter</p>
            <h2>Inspect the job stream</h2>
          </div>
          <p className="muted">Use source, keyword and job type filters to isolate opportunities.</p>
        </div>

        <form className="filters" onSubmit={handleApplyFilters}>
          <input
            name="keyword"
            placeholder="Keyword: python, ai, remote"
            value={filters.keyword}
            onChange={handleFilterChange}
          />
          <input
            name="location"
            placeholder="Location: remote, kenya, europe"
            value={filters.location}
            onChange={handleFilterChange}
          />
          <select name="source" value={filters.source} onChange={handleFilterChange}>
            <option value="">All sources</option>
            {sourceOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
          <select name="job_type" value={filters.job_type} onChange={handleFilterChange}>
            <option value="">All job types</option>
            <option value="full-time">Full-time</option>
            <option value="contract">Contract</option>
            <option value="internship">Internship</option>
            <option value="remote">Remote</option>
          </select>
          <button className="primary-button" type="submit">
            Apply Filters
          </button>
        </form>
      </section>

      <section className="analytics-row">
        <AnalyticsPanel label="Trending job titles" items={stats?.top_titles || []} />
        <AnalyticsPanel label="Trending skills" items={stats?.top_skills || []} />
        <AnalyticsPanel label="Frequent hiring companies" items={stats?.top_companies || []} />
      </section>

      <main className="content-grid">
        <section className="panel jobs-panel">
          <div className="panel-head">
            <div>
              <p className="section-kicker">Opportunity feed</p>
              <h2>Latest jobs</h2>
            </div>
            <span className="muted">{jobs.length} results</span>
          </div>

          {loading ? (
            <div className="loading-state">Loading job market data...</div>
          ) : (
            <div className="job-list">
              {jobs.map((job) => {
                const structured = buildStructuredJob(job);
                const isExpanded = expandedJobId === job.id;
                const visibleSections = isExpanded ? structured.fullSections : structured.previewSections;

                return (
                  <article className="job-card" key={job.id}>
                    <div className="job-topline">
                      <span className="source-chip">{job.source}</span>
                      <span className="muted">{new Date(job.posted_at).toLocaleDateString()}</span>
                    </div>
                    <h3>{job.title}</h3>
                    <p className="job-meta">{`${job.company} • ${job.location} • ${job.job_type}`}</p>

                    <JobStructure sections={visibleSections} />

                    <div className="tag-row">
                      {job.tags.map((tag) => (
                        <span className="tag" key={`${job.id}-${tag}`}>
                          {tag}
                        </span>
                      ))}
                    </div>

                    <div className="job-actions">
                      {structured.hasMore ? (
                        <button
                          className="secondary-button details-button"
                          type="button"
                          onClick={() => handleToggleDetails(job.id)}
                        >
                          {isExpanded ? "Show less" : "Show more"}
                        </button>
                      ) : (
                        <span className="muted details-placeholder">Compact view</span>
                      )}
                      <a className="text-link" href={job.apply_url} target="_blank" rel="noreferrer">
                        View application
                      </a>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

function StatCard({ label, value, accent }) {
  return (
    <article className={`stat-card ${accent}`}>
      <p>{label}</p>
      <strong>{value}</strong>
    </article>
  );
}

function AnalyticsPanel({ label, items }) {
  const analyticsClassName = items.some((item) => item.label.length > 18)
    ? "insight-list insight-list-two"
    : "insight-list insight-list-three";

  return (
    <section className="panel analytics-panel">
      <div className="analytics-heading">
        <p className="section-kicker">Analytics</p>
        <h2>{label}</h2>
      </div>

      {items.length ? (
        <div className={analyticsClassName}>
          {items.map((item) => (
            <div className="insight-item" key={`${label}-${item.label}`}>
              <span>{item.label} </span>
              <strong>{item.count}</strong>
            </div>
          ))}
        </div>
      ) : (
        <p className="muted">Run a scrape to generate analytics.</p>
      )}
    </section>
  );
}

function JobStructure({ sections }) {
  return (
    <div className="job-structure">
      {sections.map((section) => (
        <section className="job-section" key={section.title}>
          <h4>{section.title}</h4>
          {section.fields?.length ? (
            <div className="job-fields">
              {section.fields.map((field) => (
                <div className="job-field" key={`${section.title}-${field.label}`}>
                  <span className="field-label">{field.label}:</span>
                  <span className="field-value">{field.value}</span>
                </div>
              ))}
            </div>
          ) : null}
          {section.items?.length ? (
            <ol className="job-points">
              {section.items.map((item, index) => (
                <li key={`${section.title}-${index}`}>{item}</li>
              ))}
            </ol>
          ) : null}
        </section>
      ))}
    </div>
  );
}

function buildStructuredJob(job) {
  const description = job.description || "";
  const requirementsStart = findFirstIndex(description, [
    "requirements",
    "qualifications",
    "what you bring",
    "about you",
    "who you are",
    "skills and experience",
  ]);
  const responsibilitiesStart = findFirstIndex(description, [
    "responsibilities",
    "what you'll do",
    "what you will do",
    "your responsibilities",
    "role responsibilities",
    "what your work will focus on",
  ]);

  const orderedStarts = [responsibilitiesStart, requirementsStart]
    .filter((value) => value >= 0)
    .sort((a, b) => a - b);
  const introCutoff = orderedStarts[0] ?? description.length;

  const aboutFields = [
    { label: "Position", value: job.title },
    { label: "Type", value: humanizeValue(job.job_type) },
    { label: "Location", value: job.location },
    ...(job.salary_text ? [{ label: "Compensation", value: job.salary_text }] : []),
    ...extractTimePerWeek(description),
  ].filter((field) => field.value);

  const fullAboutItems = splitIntoPoints(description.slice(0, introCutoff));
  const fullResponsibilitiesItems = splitIntoPoints(
    sliceSection(description, responsibilitiesStart, [requirementsStart])
  );
  const fullRequirementsItems = splitIntoPoints(sliceSection(description, requirementsStart, []));

  const fullSections = [
    makeSection("About the job", aboutFields, fullAboutItems),
    makeSection("Role responsibilities", [], fullResponsibilitiesItems),
    makeSection("Requirements / qualifications", [], fullRequirementsItems),
  ].filter(Boolean);

  const previewSections = buildPreviewSections({
    aboutFields,
    aboutItems: fullAboutItems,
    responsibilitiesItems: fullResponsibilitiesItems,
    requirementsItems: fullRequirementsItems,
  });

  const fullRowCount = countSectionRows(fullSections);
  const previewRowCount = countSectionRows(previewSections);

  if (!fullSections.length) {
    return {
      previewSections: [
        {
          title: "About the job",
          fields: aboutFields,
          items: ["No clean structured details were available for this listing."],
        },
      ],
      fullSections: [
        {
          title: "About the job",
          fields: aboutFields,
          items: ["No clean structured details were available for this listing."],
        },
      ],
      hasMore: false,
    };
  }

  return {
    previewSections,
    fullSections,
    hasMore: fullRowCount > previewRowCount,
  };
}

function buildPreviewSections({ aboutFields, aboutItems, responsibilitiesItems, requirementsItems }) {
  let remaining = MAX_DETAIL_ROWS;
  const sections = [];

  const aboutFieldCount = Math.min(aboutFields.length, remaining);
  const previewAboutFields = aboutFields.slice(0, aboutFieldCount);
  remaining -= aboutFieldCount;

  const previewAboutItems = aboutItems.slice(0, Math.min(aboutItems.length, remaining));
  remaining -= previewAboutItems.length;

  if (previewAboutFields.length || previewAboutItems.length) {
    sections.push(makeSection("About the job", previewAboutFields, previewAboutItems));
  }

  const previewResponsibilities = responsibilitiesItems.slice(
    0,
    Math.min(responsibilitiesItems.length, remaining)
  );
  remaining -= previewResponsibilities.length;
  if (previewResponsibilities.length) {
    sections.push(makeSection("Role responsibilities", [], previewResponsibilities));
  }

  const previewRequirements = requirementsItems.slice(0, Math.min(requirementsItems.length, remaining));
  if (previewRequirements.length) {
    sections.push(makeSection("Requirements / qualifications", [], previewRequirements));
  }

  if (!sections.length) {
    sections.push(makeSection("About the job", aboutFields, ["No clean structured details were available for this listing."]));
  }

  return sections.filter(Boolean);
}

function makeSection(title, fields, items) {
  if (!fields.length && !items.length) {
    return null;
  }
  return { title, fields, items };
}

function countSectionRows(sections) {
  return sections.reduce(
    (total, section) => total + (section.fields?.length || 0) + (section.items?.length || 0),
    0
  );
}

function findFirstIndex(text, needles) {
  const lower = text.toLowerCase();
  const indexes = needles
    .map((needle) => lower.indexOf(needle))
    .filter((index) => index >= 0);
  return indexes.length ? Math.min(...indexes) : -1;
}

function sliceSection(text, start, laterStarts) {
  if (start < 0) {
    return "";
  }
  const validEnds = laterStarts.filter((index) => index > start);
  const end = validEnds.length ? Math.min(...validEnds) : text.length;
  return text.slice(start, end);
}

function splitIntoPoints(text) {
  return text
    .replace(/\s+/g, " ")
    .split(
      /(?:(?:^|\s)(?:requirements|qualifications|responsibilities|what you'll do|what you will do|what you bring|about you|who you are)\s*:?)|[•;]|(?<=\.)\s+(?=[A-Z0-9])/gi
    )
    .map((item) => item.trim())
    .filter((item) => item.length > 20)
    .map(cleanLeadText)
    .filter(Boolean);
}

function cleanLeadText(value) {
  return value
    .replace(
      /^(responsibilities|requirements|qualifications|what you'll do|what you will do|what you bring|about you|who you are)\s*:?\s*/i,
      ""
    )
    .trim();
}

function humanizeValue(value) {
  if (!value) {
    return "";
  }
  return value
    .split(/[-_]/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function extractTimePerWeek(description) {
  const match = description.match(
    /(\d{1,2}\s*(?:-|to)\s*\d{1,2}|\d{1,2})\s*(hours|hrs)\s*(?:per|\/)\s*week/i
  );
  if (!match) {
    return [];
  }
  return [{ label: "Time per week", value: `${match[1]} ${match[2]}/week` }];
}
