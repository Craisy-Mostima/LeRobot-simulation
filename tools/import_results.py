#!/usr/bin/env python3
"""Verify a workflow export and merge identical/new raw artifacts, never overwrite."""
import argparse
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import tempfile

import workflow as w


def import_archive(archive_path, repo):
    repo = Path(repo).resolve()
    with tempfile.TemporaryDirectory(prefix="lerobot-results-") as temporary:
        staging = Path(temporary)
        with tarfile.open(archive_path, "r:gz") as archive:
            names = set()
            for member in archive.getmembers():
                path = PurePosixPath(member.name)
                if (not member.isfile() or not path.parts or path.parts[0] != "artifacts"
                        or path.is_absolute() or ".." in path.parts or "\\" in member.name
                        or ":" in member.name or member.name in names):
                    raise ValueError(f"Unexpected archive member: {member.name}")
                names.add(member.name)
                target = staging.joinpath(*path.parts)
                if not target.resolve().is_relative_to(staging):
                    raise ValueError(f"Path escapes staging: {member.name}")
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output)
        root = staging / "artifacts"
        manifest_name = "artifacts/course_records/export_sha256.json"
        manifest = w.read_json(staging / manifest_name)
        if {"artifacts/" + name for name in manifest} != names - {manifest_name}:
            raise ValueError("Archive file list does not match checksum manifest")
        for name, digest in manifest.items():
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
                raise ValueError(f"Invalid manifest path: {name}")
            if w.sha256(root.joinpath(*path.parts)) != digest:
                raise ValueError(f"Checksum mismatch: {name}")
        for task in w.PLAN["tasks"]:
            w.validate_task(root, task)
            w.validate_result(root, task)
        pairs = [(staging / name, repo / name) for name in sorted(names)]
        # Complete preflight before writing any file to the user's repository.
        for source, target in pairs:
            if not target.resolve().is_relative_to(repo):
                raise ValueError(f"Destination escapes repository: {target}")
            if target.exists() and (not target.is_file() or w.sha256(source) != w.sha256(target)):
                raise ValueError(f"Existing evidence differs; nothing imported: {target}")
        copied = 0
        for source, target in pairs:
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                copied += 1
    w.summarize(repo / "artifacts", repo / "experiments")
    print(f"Imported {copied} new files; identical existing evidence preserved. Review all new videos before publishing.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        import_archive(args.archive, args.repo)
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError) as exc:
        parser.exit(1, f"STOP: {exc}\n")


if __name__ == "__main__":
    main()
