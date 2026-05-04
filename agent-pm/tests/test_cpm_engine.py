import datetime
import unittest

from core.cpm_engine import run_cpm
from core.calendar_engine import default_calendar_for_location
from core.llm_service import _normalise_project_classification
from core.models import Activity, Predecessor, Project


class CPMEngineTest(unittest.TestCase):
    def test_finish_to_start_uses_next_working_day(self):
        project = Project(
            project_start_date=datetime.date(2026, 7, 1),
            activities=[
                Activity(
                    activity_id="A",
                    wbs_code="1",
                    wbs_name="Test",
                    activity_name="First activity",
                    duration_most_likely_days=5,
                ),
                Activity(
                    activity_id="B",
                    wbs_code="1",
                    wbs_name="Test",
                    activity_name="Second activity",
                    duration_most_likely_days=5,
                    predecessors=[Predecessor(activity_id="A")],
                ),
            ],
        )

        run_cpm(project)

        first, second = project.activities
        self.assertEqual(first.early_finish, datetime.date(2026, 7, 7))
        self.assertEqual(second.early_start, datetime.date(2026, 7, 8))
        self.assertTrue(first.is_critical)
        self.assertTrue(second.is_critical)

    def test_parallel_non_driving_activity_has_float(self):
        project = Project(
            project_start_date=datetime.date(2026, 7, 1),
            activities=[
                Activity(activity_id="A", wbs_code="1", wbs_name="Test", activity_name="A", duration_most_likely_days=5),
                Activity(
                    activity_id="B",
                    wbs_code="1",
                    wbs_name="Test",
                    activity_name="B",
                    duration_most_likely_days=5,
                    predecessors=[Predecessor(activity_id="A")],
                ),
                Activity(
                    activity_id="C",
                    wbs_code="1",
                    wbs_name="Test",
                    activity_name="C",
                    duration_most_likely_days=1,
                    predecessors=[Predecessor(activity_id="A")],
                ),
                Activity(
                    activity_id="D",
                    wbs_code="1",
                    wbs_name="Test",
                    activity_name="D",
                    duration_most_likely_days=1,
                    predecessors=[Predecessor(activity_id="B"), Predecessor(activity_id="C")],
                ),
            ],
        )

        run_cpm(project)

        by_id = {activity.activity_id: activity for activity in project.activities}
        self.assertEqual(by_id["C"].total_float, 4)
        self.assertFalse(by_id["C"].is_critical)
        self.assertTrue(by_id["A"].is_critical)
        self.assertTrue(by_id["B"].is_critical)
        self.assertTrue(by_id["D"].is_critical)


class ProjectClassificationTest(unittest.TestCase):
    def test_residential_tower_stays_residential(self):
        brief = (
            "22-Storey Residential Tower, Adelaide. Typical floor plate 780 m2. "
            "New build residential apartments."
        )
        result = _normalise_project_classification(
            {
                "project_type": "high_rise_commercial",
                "project_name": "22-Storey Residential Tower, Adelaide",
                "summary": "A 22-storey residential tower.",
                "storeys": 22,
            },
            brief,
        )

        self.assertEqual(result["project_type"], "high_rise_residential")
        self.assertEqual(result["location"], "Adelaide")
        self.assertEqual(result["gfa_m2"], 17160)

    def test_adelaide_uses_south_australian_calendar(self):
        self.assertEqual(default_calendar_for_location("Adelaide"), "SA_5DAY_STANDARD_2026")


if __name__ == "__main__":
    unittest.main()
