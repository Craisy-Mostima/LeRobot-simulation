#!/usr/bin/env python3
"""Create labeled native-frame contact sheets; never alter original videos.

Optional local dependencies: opencv-python and Pillow. Video decoding support is
required. On Windows the Media Foundation backend also handles this experiment.
"""
import argparse
import csv
import json
from pathlib import Path
import platform
import shutil
import tempfile

import cv2
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "figures/timelines")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    plan = json.loads((ROOT / "experiments/plan.json").read_text(encoding="utf-8"))
    try:
        font = ImageFont.truetype("arial.ttf", 17)
    except OSError:
        font = ImageFont.load_default(size=17)
    rows = []
    with tempfile.TemporaryDirectory(prefix="lerobot-review-") as scratch:
        for task in plan["tasks"]:
            output = ROOT / "artifacts/custom_vla_outputs" / f"scene_{task['scene']}" / task["slug"]
            data = json.loads((output / "results.json").read_text(encoding="utf-8"))
            sheet = Image.new("RGB", (256 * 8, 44 + 288 * 5), "white")
            draw = ImageDraw.Draw(sheet)
            draw.text((8, 10), f"{task['id']} | {task['instruction']} | native 256x256 frames, playback time", fill="black", font=font)
            for item in data["results"]:
                episode = item["episode"]
                video = output / f"episode_{episode:02d}.mp4"
                copied = Path(scratch) / f"{task['id']}_{episode:02d}.mp4"
                shutil.copy2(video, copied)  # ASCII path for Windows decoder.
                backend = cv2.CAP_MSMF if platform.system() == "Windows" else cv2.CAP_ANY
                cap = cv2.VideoCapture(str(copied), backend)
                if not cap.isOpened():
                    raise RuntimeError(f"Cannot decode: {video}")
                count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                if (width, height) != (256, 256) or abs(fps - 20) > 0.01 or count != item["steps"] + 1:
                    raise ValueError(f"Unexpected video metadata: {video}")
                rows.append({"task_id": task["id"], "episode": episode, "frames": count,
                             "fps": fps, "width": width, "height": height,
                             "duration_s": round(count / fps, 3), "bytes": video.stat().st_size})
                for column, fraction in enumerate([0, .1, .2, .3, .4, .55, .75, 1]):
                    frame_index = round((count - 1) * fraction)
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                    success, frame = cap.read()
                    if not success:
                        raise RuntimeError(f"Cannot decode frame {frame_index}: {video}")
                    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                    x, y = column * 256, 44 + episode * 288
                    draw.text((x + 4, y + 5), f"E{episode:02d} {frame_index/fps:.2f}s {'PASS' if item['success'] else 'FAIL'}", fill="black", font=font)
                    sheet.paste(image, (x, y + 30))
                cap.release()
            sheet.save(args.out / f"{task['id']}.png", optimize=True)
            print(f"{task['id']}: decoded all five videos, contact sheet saved", flush=True)
    with (ROOT / "experiments/video_metadata.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
