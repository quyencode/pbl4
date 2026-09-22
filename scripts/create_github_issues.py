#!/usr/bin/env python3
"""
Tạo GitHub Issues tự động từ các Task trong README.md của dự án PBL4.

Cách dùng:
    1. Cài GitHub CLI: https://cli.github.com/  rồi đăng nhập: gh auth login
    2. Mở github_config.json, điền đúng "repo" và username GitHub thật của 4 người
    3. Xem thử trước (KHÔNG tạo gì cả, chỉ in ra để kiểm tra):
         python create_github_issues.py --dry-run
    4. Khi đã ưng ý, chạy thật (sẽ tạo label, milestone, rồi tạo toàn bộ issue):
         python create_github_issues.py --apply

Script chỉ đọc các Task nằm trong phần "TUẦN 1" → "TUẦN 10" của README.md
(bỏ qua các mục Checkpoint, Ma trận kiểm tra, Test case, Checklist merge...
vì đó không phải là một đầu việc đơn lẻ cần 1 issue riêng).
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

WEEK_RE = re.compile(r"^#\s+\d+\.\s+TUẦN\s+(\d+)", re.UNICODE)
SUBHEADER_RE = re.compile(r"^#\s+\d+\.\d+\.")
TASK_RE = re.compile(r"^##\s+Task\s+([\w\.]+)\s+–\s+(.+?)\s*$", re.UNICODE)
END_OF_WEEKS_RE = re.compile(r"^#\s+14\.")

PERSON_LABEL = {
    "Đạt": "khoi:iot",
    "Bình": "khoi:backend",
    "Lợi": "khoi:ai",
    "Quyến": "khoi:web",
    "Cả nhóm": "khoi:nhom",
}


def detect_person(line: str):
    up = line.upper()
    if "CẢ NHÓM" in up:
        return "Cả nhóm"
    if "ĐẠT" in up:
        return "Đạt"
    if "BÌNH" in up:
        return "Bình"
    if "LỢI" in up:
        return "Lợi"
    if "QUYẾN" in up:
        return "Quyến"
    return None


def parse_readme(text: str):
    lines = text.splitlines()

    # Chỉ xử lý từ tuần 1 đến hết tuần 10 (trước mục "14. MA TRẬN KIỂM TRA THEO TUẦN")
    start = next((i for i, l in enumerate(lines) if WEEK_RE.match(l)), 0)
    end = next((i for i, l in enumerate(lines) if END_OF_WEEKS_RE.match(l)), len(lines))
    lines = lines[start:end]

    tasks = []
    current_week = None
    current_person = None
    task = None
    section = None
    in_code = False

    def close_task():
        nonlocal task
        if task is not None:
            tasks.append(task)
        task = None

    i = 0
    while i < len(lines):
        line = lines[i]

        m = WEEK_RE.match(line)
        if m:
            close_task()
            current_week = int(m.group(1))
            i += 1
            continue

        if SUBHEADER_RE.match(line):
            close_task()
            current_person = None if "CHECKPOINT" in line.upper() else detect_person(line)
            i += 1
            continue

        m = TASK_RE.match(line)
        if m:
            close_task()
            task = {
                "id": m.group(1).strip(),
                "title": m.group(2).strip(),
                "week": current_week,
                "person": current_person,
                "file": [],
                "ham": [],
                "viec": [],
                "kiemtra": [],
            }
            section, in_code = None, False
            i += 1
            continue

        if task is not None:
            if line.startswith("### File"):
                section, in_code = "file", False
                i += 1
                continue
            if line.startswith("### Hàm"):
                section, in_code = "ham", False
                i += 1
                continue
            if line.startswith("### Việc cần làm"):
                section, in_code = "viec", False
                i += 1
                continue
            if line.startswith("### Kiểm tra"):
                section, in_code = "kiemtra", False
                i += 1
                continue
            if line.strip().startswith("```"):
                in_code = not in_code
                i += 1
                continue
            if section in ("file", "ham") and in_code:
                task[section].append(line.rstrip())
            elif section in ("viec", "kiemtra") and line.strip().startswith("- ["):
                task[section].append(line.strip())

        i += 1

    close_task()
    return tasks


def build_body(task: dict) -> str:
    parts = [f"**Khối phụ trách:** {task['person'] or 'Cả nhóm'}  \n**Tuần:** {task['week']}\n"]
    if task["file"]:
        parts.append("### File\n```text\n" + "\n".join(task["file"]) + "\n```")
    if task["ham"]:
        parts.append("### Hàm\n```text\n" + "\n".join(task["ham"]) + "\n```")
    if task["viec"]:
        parts.append("### Việc cần làm\n" + "\n".join(task["viec"]))
    if task["kiemtra"]:
        parts.append("### Kiểm tra\n" + "\n".join(task["kiemtra"]))
    parts.append(f"\n---\n_Tạo tự động từ `README.md`, mục Task {task['id']}._")
    return "\n\n".join(parts)


def run(cmd: list, apply: bool):
    print("  $ " + " ".join(cmd))
    if apply:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"    ⚠️  Lỗi (bỏ qua, có thể đã tồn tại): {result.stderr.strip()[:200]}")
        return result
    return None


def ensure_labels(repo, labels: dict, apply: bool):
    print("\n== Tạo label (nếu chưa có) ==")
    for name, color in labels.items():
        run(["gh", "label", "create", f"khoi:{name}", "--repo", repo, "--color", color, "--force"], apply)


def ensure_milestones(repo, weeks, apply: bool):
    print("\n== Tạo milestone theo tuần (nếu chưa có) ==")
    for w in weeks:
        run(["gh", "api", f"repos/{repo}/milestones", "-f", f"title=Tuần {w}"], apply)


def create_issue(repo, task, members, apply: bool):
    person = task["person"] or "Cả nhóm"
    label = PERSON_LABEL.get(person, "khoi:nhom")
    title = f"[Tuần {task['week']}] {person} · Task {task['id']} – {task['title']}"
    body = build_body(task)

    if person == "Cả nhóm":
        assignees = [u for u in members.values() if not u.endswith("-github-username")]
    else:
        u = members.get(person, "")
        assignees = [] if u.endswith("-github-username") or not u else [u]

    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(body)
        body_path = f.name

    cmd = [
        "gh", "issue", "create",
        "--repo", repo,
        "--title", title,
        "--body-file", body_path,
        "--label", label,
        "--milestone", f"Tuần {task['week']}",
    ]
    for a in assignees:
        cmd += ["--assignee", a]

    run(cmd, apply)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="github_config.json")
    ap.add_argument("--apply", action="store_true", help="Thực sự tạo trên GitHub (mặc định chỉ xem trước)")
    ap.add_argument("--dry-run", action="store_true", help="Chỉ xem trước, không tạo gì (mặc định)")
    ap.add_argument("--only-week", type=int, default=None, help="Chỉ xử lý 1 tuần cụ thể, vd: --only-week 1")
    args = ap.parse_args()
    apply = args.apply and not args.dry_run

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    readme_text = Path(config["readme_path"]).read_text(encoding="utf-8")
    tasks = parse_readme(readme_text)

    if args.only_week:
        tasks = [t for t in tasks if t["week"] == args.only_week]

    weeks = sorted({t["week"] for t in tasks if t["week"]})

    print(f"Đọc được {len(tasks)} task từ {config['readme_path']}, trải trên {len(weeks)} tuần.")
    if not apply:
        print("\n*** CHẾ ĐỘ XEM TRƯỚC (--dry-run) — chưa tạo gì trên GitHub. Chạy lại với --apply để tạo thật. ***")

    ensure_labels(config["repo"], config["labels"], apply)
    ensure_milestones(config["repo"], weeks, apply)

    print(f"\n== Tạo {len(tasks)} issue ==")
    for t in tasks:
        create_issue(config["repo"], t, config["members"], apply)

    print("\nXong.")
    if not apply:
        print("Không có issue nào được tạo thật (đang ở chế độ xem trước). Chạy lại với --apply khi đã sẵn sàng.")


if __name__ == "__main__":
    main()
