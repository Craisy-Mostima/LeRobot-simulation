#!/usr/bin/env python3
"""Orchestrate unmodified course scripts; use only the Python standard library.

prepare/evaluate run on the configured Linux GPU instance. summarize/export also
work on downloaded artifacts on Windows. No model downloads or installs here.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import tarfile

REPO = Path(__file__).resolve().parents[1]
PLAN = json.loads((REPO / "experiments/plan.json").read_text(encoding="utf-8"))


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def task_paths(root, task):
    base = root / "custom_libero_tasks" / f"scene_{task['scene']}" / task["slug"]
    output = root / "custom_vla_outputs" / f"scene_{task['scene']}" / task["slug"]
    return base, output


def validate_task(root, task):
    base, _ = task_paths(root, task)
    for suffix in (".json", ".bddl", ".png"):
        p = base.with_suffix(suffix)
        if not p.is_file() or p.stat().st_size == 0:
            raise ValueError(f"Missing task evidence: {p}")
    metadata = read_json(base.with_suffix(".json"))
    expected = {"scene": task["scene"], "instruction": task["instruction"],
                "base_suite": task["suite"], "base_task_id": task["base_task_id"],
                "goals": task["goals"]}
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise ValueError(f"{task['id']} metadata mismatch: {key}")
    bddl = " ".join(base.with_suffix(".bddl").read_text(encoding="utf-8").split())
    if not all(goal in bddl for goal in task["goals"]):
        raise ValueError(f"{task['id']}: expected goals absent from BDDL")
    return metadata


def validate_result(root, task):
    """Validate raw statistics and all videos. A task failure is a valid result."""
    _, output = task_paths(root, task)
    data = read_json(output / "results.json")
    protocol = PLAN["protocol"]
    expected = {"scene": task["scene"], "instruction": task["instruction"],
                "model": protocol["model"], "device": protocol["device"],
                "episodes": protocol["episodes"], "fixed_init_state": True,
                "init_state_index": protocol["init_state_index"]}
    for key, value in expected.items():
        if data.get(key) != value:
            raise ValueError(f"{task['id']} result mismatch: {key}")
    rows = data.get("results", [])
    if len(rows) != protocol["episodes"]:
        raise ValueError(f"{task['id']}: incomplete episodes")
    for index, row in enumerate(rows):
        if row.get("episode") != index or row.get("seed") != index + protocol["seed"]:
            raise ValueError(f"{task['id']}: unexpected episode/seed")
        if type(row.get("success")) is not bool:
            raise ValueError(f"{task['id']}: success must be a boolean")
        steps = row.get("steps")
        if type(steps) is not int or not 1 <= steps <= task["max_steps"]:
            raise ValueError(f"{task['id']}: invalid step count")
        video = output / f"episode_{index:02d}.mp4"
        # Raw JSON retains original cloud paths; find the copied file by basename.
        if Path(row.get("video", "")).name != video.name:
            raise ValueError(f"{task['id']}: video name mismatch")
        if not video.is_file() or video.stat().st_size == 0:
            raise ValueError(f"Missing video: {video}")
    successes = sum(row["success"] for row in rows)
    rate = data.get("success_rate")
    if type(rate) not in (int, float) or not math.isfinite(rate):
        raise ValueError(f"{task['id']}: invalid success rate")
    if data.get("n_success") != successes or abs(rate - successes / len(rows)) > 1e-9:
        raise ValueError(f"{task['id']}: inconsistent success statistics")
    return data


def verify_scripts():
    hashes = read_json(REPO / "course_scripts/SHA256.json")
    for name, expected in hashes.items():
        if sha256(REPO / "course_scripts" / name) != expected:
            raise ValueError(f"Course script changed: {name}; restore the supplied original")


def runtime_env(offline=False):
    env = os.environ.copy()
    env.update(MUJOCO_GL="egl", MPLBACKEND="Agg", PYTHONUNBUFFERED="1", HF_HUB_DISABLE_XET="1")
    env.setdefault("HF_HOME", "/root/autodl-tmp/course/huggingface")
    if offline:
        env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    return env


@contextmanager
def cloud_lock(root):
    if platform.system() != "Linux" or root.resolve() != (Path.home() / "lerobot").resolve():
        raise ValueError("Course scripts require Linux and --project-root resolving to ~/lerobot")
    import fcntl
    records = root / "course_records"
    records.mkdir(parents=True, exist_ok=True)
    with (records / ".workflow.lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("Another workflow process is running; do not start a second batch") from exc
        yield


def run_logged(command, log_path, root, *, stdin_text=None, offline=False):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("x", encoding="utf-8") as log:
        log.write("COMMAND " + json.dumps(command) + "\n")
        log.flush()
        process = subprocess.Popen(command, cwd=root, env=runtime_env(offline),
                                   stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding="utf-8", errors="replace")
        try:
            if stdin_text is not None:
                process.stdin.write(stdin_text)
                process.stdin.close()
            for line in process.stdout:
                print(line, end="", flush=True)
                log.write(line)
                log.flush()
            code = process.wait()
        except BaseException:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            raise
    if code:
        raise RuntimeError(f"Process exit {code}; inspect {log_path}. No result was fabricated.")


def stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")


def prepare(root):
    verify_scripts()
    with cloud_lock(root):
        for task in PLAN["tasks"]:
            base, output = task_paths(root, task)
            if (output / "results.json").exists():
                validate_task(root, task)
                validate_result(root, task)
                print(f"{task['id']}: completed; preserving original artifacts")
                continue
            marker = root / "course_records" / f"{task['id']}_validated.json"
            if marker.exists():
                validate_task(root, task)
                validate_marker(root, task)
                print(f"{task['id']}: already generated and validated")
                continue
            if any(base.with_suffix(suffix).exists() for suffix in (".json", ".bddl", ".png")):
                raise ValueError(f"{task['id']}: task files already exist without workflow validation; preserve and inspect them before proceeding")
            log = root / "course_records" / f"{task['id']}_prepare_{stamp()}.log"
            run_logged([sys.executable, "-u", str(REPO / "course_scripts/libero_custom_task_builder.py")],
                       log, root, stdin_text=f"{task['scene']}\n{task['instruction']}\ny\n")
            validate_task(root, task)
            if "Initial goal already satisfied?: False" not in log.read_text(encoding="utf-8"):
                raise ValueError(f"{task['id']}: initial-goal check did not confirm False; inspect {log}")
            write_json(marker, {"task_id": task["id"], "initial_goal_satisfied": False,
                                "log": log.name,
                                "files": {suffix: sha256(base.with_suffix(suffix)) for suffix in (".json", ".bddl", ".png")}})
    print("PREPARE COMPLETE. Inspect all four new previews/goals before running evaluate.")


def validate_marker(root, task):
    base, _ = task_paths(root, task)
    marker = read_json(root / "course_records" / f"{task['id']}_validated.json")
    if marker.get("initial_goal_satisfied") is not False:
        raise ValueError(f"{task['id']}: no valid initial-goal check")
    for suffix in (".json", ".bddl", ".png"):
        if marker.get("files", {}).get(suffix) != sha256(base.with_suffix(suffix)):
            raise ValueError(f"{task['id']}: task changed since validation")


def snapshot_environment(root):
    directory = root / "course_records" / f"environment_{stamp()}"
    directory.mkdir(parents=True)
    for name, command in {
        "pip-freeze.txt": [sys.executable, "-m", "pip", "freeze"],
        "nvidia-smi.txt": ["nvidia-smi"],
        "lerobot-revision.txt": ["git", "rev-parse", "HEAD"],
        "lerobot-version.txt": ["git", "describe", "--tags", "--always"],
    }.items():
        result = subprocess.run(command, cwd=root, capture_output=True, text=True, check=True)
        (directory / name).write_text(result.stdout, encoding="utf-8")
    write_json(directory / "runtime.json", {"utc": stamp(), "python": sys.version,
                "python_executable": sys.executable, "platform": platform.platform(),
                "protocol": PLAN["protocol"], "course_scripts_sha256": read_json(REPO / "course_scripts/SHA256.json"),
                "environment": {k: runtime_env(True)[k] for k in ("HF_HOME", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "MUJOCO_GL", "MPLBACKEND")}})


def evaluate(root):
    verify_scripts()
    with cloud_lock(root):
        pending = []
        # Check the entire batch before loading any model.
        for task in PLAN["tasks"]:
            metadata = validate_task(root, task)
            base, _ = task_paths(root, task)
            bddl_path = Path(metadata.get("bddl_file", "")).expanduser()
            if not bddl_path.is_absolute():
                bddl_path = base.parent / bddl_path
            if bddl_path.resolve() != base.with_suffix(".bddl").resolve():
                raise ValueError(f"{task['id']}: metadata points to a different BDDL; regenerate on this instance")
            _, output = task_paths(root, task)
            if (output / "results.json").exists():
                validate_result(root, task)
                print(f"{task['id']}: complete, SKIP (never overwrite)")
            else:
                validate_marker(root, task)
                if output.exists() and any(output.iterdir()):
                    raise ValueError(f"{task['id']}: incomplete output at {output}. Archive it before retrying; nothing overwritten.")
                pending.append(task)
        if pending:
            snapshot_environment(root)
        for task in pending:
            base, _ = task_paths(root, task)
            command = [sys.executable, "-u", str(REPO / "course_scripts/custom_vla_eval.py"),
                       "--task", str(base.with_suffix(".json")), "--model", PLAN["protocol"]["model"],
                       "--episodes", "5", "--device", "cuda", "--seed", "0", "--init-state-index", "0"]
            print(f"\nSTART {task['id']}: {task['instruction']}", flush=True)
            run_logged(command, root / "course_records" / f"{task['id']}_eval_{stamp()}.log", root, offline=True)
            data = validate_result(root, task)
            print(f"FINISHED {task['id']}: {data['n_success']}/5", flush=True)
    print("BATCH COMPLETE. Run export, then download the archive before shutting down.")


def summarize(root, destination):
    destination.mkdir(parents=True, exist_ok=True)
    rows = []
    for task in PLAN["tasks"]:
        _, output = task_paths(root, task)
        row = {"task_id": task["id"], "scene": task["scene"], "instruction": task["instruction"],
               "status": "pending", "episodes": "", "successes": "", "success_rate_percent": "",
               "max_steps": task["max_steps"], "error": ""}
        if output.exists() and any(output.iterdir()):
            try:
                validate_task(root, task)
                data = validate_result(root, task)
                row.update(status="completed", episodes=data["episodes"], successes=data["n_success"],
                           success_rate_percent=100 * data["success_rate"])
            except (ValueError, OSError, TypeError, KeyError) as exc:
                row.update(status="incomplete_or_invalid", error=str(exc))
        rows.append(row)
    with (destination / "summary.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    write_json(destination / "summary.json", rows)
    print(json.dumps(rows, indent=2, ensure_ascii=False))
    return rows


def export(root, destination):
    """Require all five complete tasks; include raw videos without transcoding."""
    destination = destination.resolve()
    if destination.exists():
        raise ValueError(f"Export destination already exists: {destination}")
    for task in PLAN["tasks"]:
        validate_task(root, task)
        validate_result(root, task)
    destination.parent.mkdir(parents=True, exist_ok=True)
    export_summary = root / "course_records" / "batch_summary"
    summarize(root, export_summary)
    files = set()
    for task in PLAN["tasks"]:
        base, output = task_paths(root, task)
        files.update(base.with_suffix(suffix) for suffix in (".bddl", ".json", ".png"))
        files.update(output / f"episode_{i:02d}.mp4" for i in range(PLAN["protocol"]["episodes"]))
        files.add(output / "results.json")
    # Explicit record extensions: never collect cache directories or credentials.
    records = root / "course_records"
    files.update(p for p in records.rglob("*") if p.is_file() and p.name != "export_sha256.json" and p.suffix in {".log", ".txt", ".json", ".csv"})
    manifest = {p.relative_to(root).as_posix(): sha256(p) for p in sorted(files)}
    manifest_path = records / "export_sha256.json"
    write_json(manifest_path, manifest)
    files.add(manifest_path)
    with tarfile.open(destination, "x:gz") as archive:
        for path in sorted(files):
            archive.add(path, arcname=(Path("artifacts") / path.relative_to(root)).as_posix(), recursive=False)
    print(f"DOWNLOAD THIS FILE: {destination}\nSHA256: {sha256(destination)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "evaluate", "summarize", "export"])
    parser.add_argument("--project-root", type=Path, default=Path.home() / "lerobot")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    root = args.project_root.resolve()
    if not root.is_dir():
        parser.error(f"Project root does not exist: {root}")
    try:
        if args.action == "prepare":
            prepare(root)
        elif args.action == "evaluate":
            evaluate(root)
        elif args.action == "summarize":
            summarize(root, args.out or REPO / "experiments")
        else:
            export(root, args.out or root.parent / "course_all_results.tar.gz")
    except (ValueError, OSError, RuntimeError, TypeError, KeyError) as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
