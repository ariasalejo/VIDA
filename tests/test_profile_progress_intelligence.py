import unittest

from vida_engines import (
    CourseEngine,
    CourseProfile,
    IntelligenceEngine,
    ProfileEngine,
    ProgressEngine,
)


class TestCourseProfile(unittest.TestCase):

    def setUp(self):
        self.profile = ProfileEngine(
            "data/profiles/sena_ciberseguridad.json"
        ).load()

    def test_profile_identity(self):
        self.assertEqual(
            self.profile.course_id,
            "sena_ciberseguridad",
        )

        self.assertEqual(
            self.profile.name,
            "Ciberseguridad",
        )

    def test_profile_weights(self):
        self.assertAlmostEqual(
            self.profile.weight("video"),
            0.20,
        )

        self.assertAlmostEqual(
            self.profile.weight("activity"),
            0.40,
        )

        self.assertAlmostEqual(
            self.profile.weight("mastery"),
            0.25,
        )

        self.assertAlmostEqual(
            self.profile.weight("evidence"),
            0.15,
        )

        self.assertAlmostEqual(
            self.profile.total_weight(),
            1.0,
        )


class TestProgressEngine(unittest.TestCase):

    def setUp(self):
        self.profile = ProfileEngine(
            "data/profiles/sena_ciberseguridad.json"
        ).load()

    def test_empty_progress(self):
        result = ProgressEngine().calculate(
            completed_videos=0,
            total_videos=10,
            completed_activities=0,
            total_activities=10,
            verified_concepts=0,
            total_concepts=10,
            evidence_count=0,
            profile=self.profile,
        )

        self.assertEqual(result.operational, 0)
        self.assertEqual(result.mastery, 0)
        self.assertEqual(result.evidence_count, 0)

    def test_complete_progress(self):
        result = ProgressEngine().calculate(
            completed_videos=10,
            total_videos=10,
            completed_activities=10,
            total_activities=10,
            verified_concepts=10,
            total_concepts=10,
            evidence_count=5,
            profile=self.profile,
        )

        self.assertEqual(result.operational, 100)
        self.assertEqual(result.mastery, 100)
        self.assertEqual(result.evidence_strength, 1.0)

    def test_profile_weights_affect_operational_score(self):
        result = ProgressEngine().calculate(
            completed_videos=10,
            total_videos=10,
            completed_activities=0,
            total_activities=10,
            profile=self.profile,
        )

        # Activity pesa 0.40 y video 0.20.
        # Con ambos disponibles:
        # (1*0.20 + 0*0.40) / 0.60 = 0.333...
        self.assertEqual(result.operational, 33)

    def test_zero_total_is_not_available(self):
        result = ProgressEngine().calculate(
            completed_videos=0,
            total_videos=0,
            completed_activities=0,
            total_activities=0,
            profile=self.profile,
        )

        self.assertFalse(result.video_available)
        self.assertFalse(result.activity_available)
        self.assertEqual(result.operational, 0)


class TestIntelligenceEngine(unittest.TestCase):

    def setUp(self):
        self.profile = ProfileEngine(
            "data/profiles/sena_ciberseguridad.json"
        ).load()

        self.engine = IntelligenceEngine(
            profile=self.profile
        )

    def test_curricular_weights_come_from_profile(self):
        self.assertAlmostEqual(
            self.engine._weight("video"),
            0.20,
        )

        self.assertAlmostEqual(
            self.engine._weight("activity"),
            0.40,
        )

        self.assertAlmostEqual(
            self.engine._weight("mastery"),
            0.25,
        )

        self.assertAlmostEqual(
            self.engine._weight("evidence"),
            0.15,
        )

    def test_intelligence_internal_weights_are_preserved(self):
        self.assertAlmostEqual(
            self.engine._weight("consistency"),
            0.8,
        )

        self.assertAlmostEqual(
            self.engine._weight("stagnation"),
            1.0,
        )

    def test_signals_are_generated(self):
        course = {
            "videos": [
                {"id": "v1"},
                {"id": "v2"},
            ],
            "items": [
                {"id": "a1", "kind": "activity"},
                {"id": "a2", "kind": "activity"},
            ],
            "concepts": [
                {"id": "c1"},
                {"id": "c2"},
            ],
        }

        signals = self.engine.signals(
            course=course,
            completed_video_ids={"v1"},
            completed_activity_ids={"a1"},
            verified_concepts={"c1"},
            evidence_count=1,
        )

        names = {
            signal.name
            for signal in signals
        }

        expected = {
            "video_progress",
            "activity_progress",
            "concept_mastery",
            "evidence_strength",
            "consistency",
            "stagnation",
            "unknown_pressure",
        }

        self.assertEqual(names, expected)


if __name__ == "__main__":
    unittest.main()


class TestCourseProfileValidation(unittest.TestCase):

    def test_empty_course_id_is_rejected(self):
        profile = CourseProfile(
            course_id="",
            name="Ciberseguridad",
        )

        with self.assertRaises(ValueError):
            profile.validate()

    def test_empty_name_is_rejected(self):
        profile = CourseProfile(
            course_id="test",
            name="",
        )

        with self.assertRaises(ValueError):
            profile.validate()

    def test_negative_weight_is_rejected(self):
        profile = CourseProfile(
            course_id="test",
            name="Test",
            components={"videos": True},
            weights={"video": -0.1},
        )

        with self.assertRaises(ValueError):
            profile.validate()

    def test_non_numeric_weight_is_rejected(self):
        profile = CourseProfile(
            course_id="test",
            name="Test",
            components={"videos": True},
            weights={"video": "abc"},
        )

        with self.assertRaises(ValueError):
            profile.validate()

    def test_infinite_weight_is_rejected(self):
        profile = CourseProfile(
            course_id="test",
            name="Test",
            components={"videos": True},
            weights={"video": float("inf")},
        )

        with self.assertRaises(ValueError):
            profile.validate()

    def test_weight_without_enabled_component_is_rejected(self):
        profile = CourseProfile(
            course_id="test",
            name="Test",
            components={"videos": False},
            weights={"video": 0.20},
        )

        with self.assertRaises(ValueError):
            profile.validate()

    def test_weights_above_one_are_rejected(self):
        profile = CourseProfile(
            course_id="test",
            name="Test",
            components={
                "videos": True,
                "activities": True,
            },
            weights={
                "video": 0.70,
                "activity": 0.40,
            },
        )

        with self.assertRaises(ValueError):
            profile.validate()

    def test_valid_profile_passes(self):
        profile = CourseProfile(
            course_id="test",
            name="Test",
            components={
                "videos": True,
                "activities": True,
                "concepts": True,
                "evidence": True,
            },
            weights={
                "video": 0.20,
                "activity": 0.40,
                "mastery": 0.25,
                "evidence": 0.15,
            },
        )

        profile.validate()


if __name__ == "__main__":
    unittest.main()


class TestProfileEngine(unittest.TestCase):

    def test_load_real_sena_profile(self):
        engine = ProfileEngine(
            "data/profiles/sena_ciberseguridad.json"
        )

        profile = engine.load()

        self.assertIsInstance(profile, CourseProfile)
        self.assertEqual(profile.course_id, "sena_ciberseguridad")
        self.assertEqual(profile.name, "Ciberseguridad")

    def test_loaded_profile_is_valid(self):
        profile = ProfileEngine(
            "data/profiles/sena_ciberseguridad.json"
        ).load()

        profile.validate()

        self.assertAlmostEqual(
            profile.total_weight(),
            1.0,
        )

    def test_missing_profile_is_rejected(self):
        engine = ProfileEngine(
            "data/profiles/archivo_que_no_existe.json"
        )

        with self.assertRaises((FileNotFoundError, ValueError)):
            engine.load()

    def test_profile_components_are_available(self):
        profile = ProfileEngine(
            "data/profiles/sena_ciberseguridad.json"
        ).load()

        self.assertTrue(profile.has_component("videos"))
        self.assertTrue(profile.has_component("activities"))
        self.assertTrue(profile.has_component("concepts"))
        self.assertTrue(profile.has_component("evidence"))
        self.assertTrue(profile.has_component("projects"))
        self.assertTrue(profile.has_component("certification"))

    def test_profile_is_frozen(self):
        profile = ProfileEngine(
            "data/profiles/sena_ciberseguridad.json"
        ).load()

        with self.assertRaises(Exception):
            profile.course_id = "otro_curso"


if __name__ == "__main__":
    unittest.main()


class TestCourseEngine(unittest.TestCase):

    def setUp(self):
        self.engine = CourseEngine("data/course.json")

    def test_load_real_course_manifest(self):
        course = self.engine.load()

        self.assertIsInstance(course, dict)

    def test_course_manifest_contains_expected_sections(self):
        course = self.engine.load()

        self.assertIn("videos", course)
        self.assertIn("items", course)
        self.assertIn("concepts", course)

    def test_videos_returns_list(self):
        videos = self.engine.videos()

        self.assertIsInstance(videos, list)

        for video in videos:
            self.assertIsInstance(video, dict)

    def test_activities_filter_items(self):
        activities = self.engine.activities()

        self.assertIsInstance(activities, list)

        for activity in activities:
            self.assertIsInstance(activity, dict)
            self.assertEqual(
                activity.get("kind"),
                "activity",
            )

    def test_concepts_returns_list(self):
        concepts = self.engine.concepts()

        self.assertIsInstance(concepts, list)

        for concept in concepts:
            self.assertIsInstance(concept, dict)

    def test_missing_manifest_is_rejected(self):
        engine = CourseEngine(
            "data/manifest_que_no_existe.json"
        )

        with self.assertRaises(FileNotFoundError):
            engine.load()


if __name__ == "__main__":
    unittest.main()


class TestCourseEngine(unittest.TestCase):

    def setUp(self):
        self.engine = CourseEngine("data/course.json")

    def test_load_real_course_manifest(self):
        course = self.engine.load()

        self.assertIsInstance(course, dict)

    def test_course_manifest_contains_expected_sections(self):
        course = self.engine.load()

        self.assertIn("videos", course)
        self.assertIn("items", course)
        self.assertIn("concepts", course)

    def test_videos_returns_list(self):
        videos = self.engine.videos()

        self.assertIsInstance(videos, list)

        for video in videos:
            self.assertIsInstance(video, dict)

    def test_activities_filter_items(self):
        activities = self.engine.activities()

        self.assertIsInstance(activities, list)

        for activity in activities:
            self.assertIsInstance(activity, dict)
            self.assertEqual(
                activity.get("kind"),
                "activity",
            )

    def test_concepts_returns_list(self):
        concepts = self.engine.concepts()

        self.assertIsInstance(concepts, list)

        for concept in concepts:
            self.assertIsInstance(concept, dict)

    def test_missing_manifest_is_rejected(self):
        engine = CourseEngine(
            "data/manifest_que_no_existe.json"
        )

        with self.assertRaises(FileNotFoundError):
            engine.load()


if __name__ == "__main__":
    unittest.main()


class TestCourseProgressIntegration(unittest.TestCase):

    def setUp(self):
        self.profile = ProfileEngine(
            "data/profiles/sena_ciberseguridad.json"
        ).load()

        self.course = CourseEngine(
            "data/course.json"
        )

        self.progress = ProgressEngine()

    def test_real_course_counts_feed_progress_engine(self):
        videos = self.course.videos()
        activities = self.course.activities()
        concepts = self.course.concepts()

        result = self.progress.calculate(
            completed_videos=0,
            total_videos=len(videos),
            completed_activities=0,
            total_activities=len(activities),
            verified_concepts=0,
            total_concepts=len(concepts),
            evidence_count=0,
            profile=self.profile,
        )

        self.assertEqual(result.operational, 0)
        self.assertEqual(result.mastery, 0)

        self.assertEqual(
            result.video_progress,
            0.0,
        )

        self.assertEqual(
            result.activity_progress,
            0.0,
        )

        self.assertEqual(
            result.concept_progress,
            0.0,
        )

    def test_real_course_completion_reaches_100(self):
        videos = self.course.videos()
        activities = self.course.activities()
        concepts = self.course.concepts()

        result = self.progress.calculate(
            completed_videos=len(videos),
            total_videos=len(videos),
            completed_activities=len(activities),
            total_activities=len(activities),
            verified_concepts=len(concepts),
            total_concepts=len(concepts),
            evidence_count=5,
            profile=self.profile,
        )

        self.assertEqual(result.operational, 100)
        self.assertEqual(result.mastery, 100)
        self.assertEqual(result.evidence_strength, 1.0)


if __name__ == "__main__":
    unittest.main()
