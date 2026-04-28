import unittest
from pathlib import Path

from app.models import JobSource
from app.services.job_store import JobStore
from app.services.normalizer import normalize_job


class PipelineTests(unittest.TestCase):
    def test_normalize_job_extracts_required_fields(self):
        job = normalize_job(
            {
                "title": "Senior Python Engineer",
                "company": "Acme Labs",
                "location": "Remote",
                "description": "<p>Full Time role with 6 years experience using Python, FastAPI, AWS and Docker.</p>",
                "job_url": "https://example.com/jobs/123",
                "apply_url": "https://example.com/jobs/123/apply",
                "salary_text": "USD 120000 - 150000 per year",
                "posted_at": "2026-04-20",
            },
            JobSource.remoteok,
        )

        self.assertEqual(job.job_type, "full-time")
        self.assertEqual(job.workplace_type.value, "remote")
        self.assertEqual(job.experience_level.value, "senior")
        self.assertIn("python", job.skills)
        self.assertIn("fastapi", job.skills)
        self.assertEqual(job.salary_currency, "USD")
        self.assertEqual(job.salary_min, 120000.0)
        self.assertEqual(job.salary_max, 150000.0)
        self.assertTrue(job.description_sections)

    def test_merge_jobs_prefers_more_complete_duplicate(self):
        temp_path = Path(__file__).with_name("test_jobs.json")
        try:
            store = JobStore(temp_path)
            initial = normalize_job(
                {
                    "title": "Backend Engineer",
                    "company": "Acme",
                    "location": "Remote",
                    "description": "Python backend role",
                    "job_url": "https://example.com/jobs/1",
                    "apply_url": "https://example.com/jobs/1/apply",
                    "posted_at": "2026-04-01",
                },
                JobSource.remoteok,
            )
            enriched = normalize_job(
                {
                    "title": "Backend Engineer",
                    "company": "Acme",
                    "location": "Remote",
                    "description": "Senior Python backend role with FastAPI and AWS",
                    "job_url": "https://example.com/jobs/1?utm_source=test",
                    "apply_url": "https://example.com/jobs/1/apply",
                    "posted_at": "2026-04-01",
                },
                JobSource.greenhouse,
            )

            first_result = store.merge_jobs([initial], JobSource.remoteok)
            second_result = store.merge_jobs([enriched], JobSource.greenhouse)
            saved_jobs = store.all_jobs()

            self.assertEqual(first_result.inserted, 1)
            self.assertEqual(second_result.inserted, 0)
            self.assertEqual(second_result.updated, 1)
            self.assertEqual(second_result.deduplicated, 1)
            self.assertEqual(len(saved_jobs), 1)
            self.assertIn("fastapi", saved_jobs[0].skills)
            self.assertIn("aws", saved_jobs[0].skills)
        finally:
            temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
