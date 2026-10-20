"""Integrity tests use temporary fake evidence; never run GPU inference."""
import ast
from contextlib import nullcontext, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import re
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("workflow", REPO / "tools/workflow.py")
w = importlib.util.module_from_spec(spec)
sys.modules["workflow"] = w
spec.loader.exec_module(w)
import_spec = importlib.util.spec_from_file_location("import_results", REPO / "tools/import_results.py")
importer = importlib.util.module_from_spec(import_spec)
import_spec.loader.exec_module(importer)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "source"
        self.root.mkdir()

    def fixture(self, task, completed=True, successes=0):
        base, output = w.task_paths(self.root, task)
        base.parent.mkdir(parents=True, exist_ok=True)
        w.write_json(base.with_suffix(".json"), {
            "scene": task["scene"], "instruction": task["instruction"],
            "base_suite": task["suite"], "base_task_id": task["base_task_id"], "goals": task["goals"],
            "bddl_file": str(base.with_suffix(".bddl"))})
        base.with_suffix(".bddl").write_text("(:goal (And " + " ".join(task["goals"]) + "))", encoding="utf-8")
        base.with_suffix(".png").write_bytes(b"fake-preview-for-integrity-test-only")
        w.write_json(self.root / "course_records" / f"{task['id']}_validated.json", {
            "initial_goal_satisfied": False,
            "files": {suffix: w.sha256(base.with_suffix(suffix)) for suffix in (".json", ".bddl", ".png")}})
        output.mkdir(parents=True)
        if not completed:
            (output / "episode_00.mp4").write_bytes(b"partial-video-test")
            return
        rows = []
        for i in range(5):
            (output / f"episode_{i:02d}.mp4").write_bytes(b"fake-video-for-integrity-test-only")
            rows.append({"episode": i, "seed": i, "steps": 100 if i < successes else task["max_steps"],
                         "success": i < successes,
                         "video": f"/root/lerobot/custom_vla_outputs/scene_{task['scene']}/{task['slug']}/episode_{i:02d}.mp4"})
        w.write_json(output / "results.json", {
            "scene": task["scene"], "instruction": task["instruction"], "model": "lerobot/smolvla_libero",
            "device": "cuda", "episodes": 5, "fixed_init_state": True, "init_state_index": 0,
            "results": rows, "n_success": successes, "success_rate": successes / 5})

    def test_course_scripts_unchanged_and_plan_supported_by_original_parsers(self):
        w.verify_scripts()
        original = REPO / "course_scripts/libero_custom_task_builder.py"
        tree = ast.parse(original.read_text(encoding="utf-8"))
        wanted = {"normalize_text", "contains_any", "find_all_entities", "clean_instruction",
                  "parse_scene_a", "parse_scene_b", "parse_scene_c", "slugify"}
        module = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted], type_ignores=[])
        namespace = {"re": re}
        exec(compile(module, str(original), "exec"), namespace)
        for task in w.PLAN["tasks"]:
            self.assertEqual(namespace["slugify"](task["instruction"]), task["slug"])
            self.assertEqual(namespace[f"parse_scene_{task['scene'].lower()}"](task["instruction"])[0], task["goals"])

    def test_zero_success_is_completed_and_pending_is_not_zero(self):
        self.fixture(w.PLAN["tasks"][0], successes=0)
        with redirect_stdout(io.StringIO()):
            rows = w.summarize(self.root, self.root / "summary")
        self.assertEqual(rows[0]["status"], "completed")
        self.assertEqual(rows[0]["success_rate_percent"], 0)
        self.assertEqual(rows[1]["status"], "pending")
        self.assertEqual(rows[1]["success_rate_percent"], "")

    def test_missing_video_and_inconsistent_statistics_rejected(self):
        task = w.PLAN["tasks"][0]
        self.fixture(task, successes=2)
        _, output = w.task_paths(self.root, task)
        data = w.read_json(output / "results.json")
        data["n_success"] = 3
        w.write_json(output / "results.json", data)
        with self.assertRaisesRegex(ValueError, "inconsistent"):
            w.validate_result(self.root, task)
        data["n_success"] = 2
        w.write_json(output / "results.json", data)
        (output / "episode_04.mp4").unlink()
        with self.assertRaisesRegex(ValueError, "Missing video"):
            w.validate_result(self.root, task)

    def test_seed_protocol_and_nonfinite_rate_rejected(self):
        task = w.PLAN["tasks"][0]
        self.fixture(task)
        _, output = w.task_paths(self.root, task)
        data = w.read_json(output / "results.json")
        data["results"][1]["seed"] = 99
        w.write_json(output / "results.json", data)
        with self.assertRaisesRegex(ValueError, "episode/seed"):
            w.validate_result(self.root, task)
        data["results"][1]["seed"] = 1
        data["success_rate"] = float("nan")
        w.write_json(output / "results.json", data)
        with self.assertRaisesRegex(ValueError, "invalid success rate"):
            w.validate_result(self.root, task)

    def test_partial_run_is_not_overwritten_or_started(self):
        for index, task in enumerate(w.PLAN["tasks"]):
            self.fixture(task, completed=index != 1)
        _, output = w.task_paths(self.root, w.PLAN["tasks"][1])
        original = (output / "episode_00.mp4").read_bytes()
        with patch.object(w, "cloud_lock", return_value=nullcontext()), patch.object(w, "run_logged") as launch:
            with redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, "incomplete output"):
                w.evaluate(self.root)
            launch.assert_not_called()
        self.assertEqual((output / "episode_00.mp4").read_bytes(), original)

    def test_all_completed_never_runs_evaluator(self):
        for task in w.PLAN["tasks"]:
            self.fixture(task)
        with patch.object(w, "cloud_lock", return_value=nullcontext()), patch.object(w, "run_logged") as launch:
            with redirect_stdout(io.StringIO()):
                w.evaluate(self.root)
            launch.assert_not_called()

    def test_export_contains_25_original_videos_and_valid_manifest_even_on_second_export(self):
        for task in w.PLAN["tasks"]:
            self.fixture(task)
        for i in range(2):
            target = Path(self.tmp.name) / f"export_{i}.tar.gz"
            with redirect_stdout(io.StringIO()):
                w.export(self.root, target)
            with tarfile.open(target) as archive:
                names = archive.getnames()
                self.assertEqual(sum(name.endswith(".mp4") for name in names), 25)
                manifest = json.load(archive.extractfile("artifacts/course_records/export_sha256.json"))
                self.assertNotIn("course_records/export_sha256.json", manifest)
                for name, digest in manifest.items():
                    import hashlib
                    self.assertEqual(hashlib.sha256(archive.extractfile("artifacts/" + name).read()).hexdigest(), digest)
            with self.assertRaisesRegex(ValueError, "already exists"):
                w.export(self.root, target)

    def test_export_refuses_unfinished_batch(self):
        self.fixture(w.PLAN["tasks"][0])
        destination = Path(self.tmp.name) / "incomplete.tar.gz"
        with self.assertRaises(ValueError):
            w.export(self.root, destination)
        self.assertFalse(destination.exists())

    def test_preview_changed_since_generation_blocks_evaluation(self):
        task = w.PLAN["tasks"][0]
        self.fixture(task)
        base, _ = w.task_paths(self.root, task)
        base.with_suffix(".png").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "task changed"):
            w.validate_marker(self.root, task)

    def complete_archive(self):
        for task in w.PLAN["tasks"]:
            self.fixture(task)
        archive = Path(self.tmp.name) / "results.tar.gz"
        with redirect_stdout(io.StringIO()):
            w.export(self.root, archive)
        return archive

    def test_import_accepts_complete_archive_and_is_idempotent(self):
        archive = self.complete_archive()
        destination = Path(self.tmp.name) / "repository"
        for _ in range(2):
            with redirect_stdout(io.StringIO()):
                importer.import_archive(archive, destination)
        self.assertEqual(len(list(destination.rglob("*.mp4"))), 25)
        self.assertEqual(len(w.read_json(destination / "experiments/summary.json")), 5)

    def test_import_conflict_preserves_existing_file_and_writes_nothing(self):
        archive = self.complete_archive()
        destination = Path(self.tmp.name) / "repository"
        _, output = w.task_paths(destination / "artifacts", w.PLAN["tasks"][0])
        output.mkdir(parents=True)
        old = output / "episode_00.mp4"
        old.write_bytes(b"different original evidence")
        with self.assertRaisesRegex(ValueError, "Existing evidence differs"):
            importer.import_archive(archive, destination)
        self.assertEqual(old.read_bytes(), b"different original evidence")
        self.assertEqual([p for p in destination.rglob("*") if p.is_file()], [old])

    def test_import_rejects_tampered_video(self):
        original = self.complete_archive()
        modified = Path(self.tmp.name) / "tampered.tar.gz"
        changed = False
        with tarfile.open(original) as source, tarfile.open(modified, "w:gz") as target:
            for member in source.getmembers():
                content = source.extractfile(member).read()
                if member.name.endswith(".mp4") and not changed:
                    content = b"modified video"
                    member.size = len(content)
                    changed = True
                target.addfile(member, io.BytesIO(content))
        destination = Path(self.tmp.name) / "repository"
        with self.assertRaisesRegex(ValueError, "Checksum mismatch"):
            importer.import_archive(modified, destination)
        self.assertFalse(destination.exists())

    def test_import_rejects_archive_traversal(self):
        malicious = Path(self.tmp.name) / "malicious.tar.gz"
        with tarfile.open(malicious, "w:gz") as archive:
            member = tarfile.TarInfo("artifacts/../../escape.txt")
            member.size = 1
            archive.addfile(member, io.BytesIO(b"x"))
        with self.assertRaisesRegex(ValueError, "Unexpected archive member"):
            importer.import_archive(malicious, Path(self.tmp.name) / "repository")


if __name__ == "__main__":
    unittest.main()
