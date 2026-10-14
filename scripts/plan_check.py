"""Kiểm tra kế hoạch (docs/plan/backlog.md) một cách tự động.

Kiểm tra:
  1. Phụ thuộc trỏ tới task không tồn tại.
  2. Vòng lặp phụ thuộc.
  3. Thứ tự sprint: task phụ thuộc phải bắt đầu không muộn hơn task dùng nó.
  4. Mỗi task trong backlog có task card trong docs/plan/epics/ và ngược lại.
  5. Tải công việc từng vai trò theo từng sprint so với sức chứa.
  6. Đường găng (chuỗi phụ thuộc dài nhất theo ngày công).

Dùng:
  uv run python scripts/plan_check.py            # báo cáo đầy đủ
  uv run python scripts/plan_check.py --board    # chỉ bảng trạng thái
  uv run python scripts/plan_check.py --util 0.6 # đổi tỷ lệ thời gian dành cho dự án

Thoát với mã 1 nếu có lỗi (dùng được trong CI).
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKLOG = ROOT / "docs" / "plan" / "backlog.md"
EPICS = ROOT / "docs" / "plan" / "epics"

SPRINTS = ["S0", "S1", "S2", "S3", "DP"]
SPRINT_DAYS = {"S0": 3, "S1": 8, "S2": 7, "S3": 3, "DP": 1}
ID_RE = re.compile(r"\b([A-Z]{3,5}-\d{2})\b")
ROLE_RE = re.compile(r"\bM[1-5]\b")


@dataclass
class Task:
    id: str
    title: str
    roles: list[str]
    owner: str
    days: float
    sprints: list[str]
    priority: str
    deps: list[str]
    status: str
    starred: bool
    line: int
    raw_deps: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def start(self) -> int:
        return SPRINTS.index(self.sprints[0])

    @property
    def end(self) -> int:
        return SPRINTS.index(self.sprints[-1])


def parse_sprints(cell: str) -> list[str]:
    found = re.findall(r"S[0-3]|DP", cell)
    if not found:
        raise ValueError(f"không đọc được sprint: {cell!r}")
    lo, hi = SPRINTS.index(found[0]), SPRINTS.index(found[-1])
    return SPRINTS[lo : hi + 1]


def parse_roles(cell: str) -> list[str]:
    main = re.sub(r"\(.*?\)", "", cell)  # bỏ phần (+người hỗ trợ)
    return sorted(set(ROLE_RE.findall(main)))


def parse_backlog(path: Path = BACKLOG) -> list[Task]:
    tasks: list[Task] = []
    header: list[str] | None = None
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.startswith("|"):
            header = None if not line.strip() else header
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0] == "Mã":
            header = cells
            continue
        if header is None or set(line.replace("|", "").strip()) <= {"-", " "}:
            continue
        row = dict(zip(header, cells, strict=False))
        m = ID_RE.search(row.get("Mã", ""))
        if not m:
            continue
        tasks.append(
            Task(
                id=m.group(1),
                title=row.get("Task", ""),
                roles=parse_roles(row.get("Vai trò", "")),
                owner=row.get("Người", ""),
                days=float(row.get("Ngày công", "0").replace(",", ".")),
                sprints=parse_sprints(row.get("Sprint", "")),
                priority=row.get("Ưu tiên", ""),
                deps=ID_RE.findall(row.get("Phụ thuộc", "")),
                raw_deps=row.get("Phụ thuộc", ""),
                status=row.get("Trạng thái", "").strip("` "),
                starred="★" in row.get("Mã", ""),
                line=i,
            )
        )
    return tasks


def card_ids(epics_dir: Path = EPICS) -> set[str]:
    ids: set[str] = set()
    for f in sorted(epics_dir.glob("*.md")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.startswith("### "):
                m = ID_RE.search(line)
                if m:
                    ids.add(m.group(1))
    return ids


def card_headers(epics_dir: Path = EPICS) -> dict[str, dict[str, str]]:
    """Đọc bảng thông tin ngay dưới tiêu đề '### MÃ · …' của mỗi task card."""
    cards: dict[str, dict[str, str]] = {}
    for f in sorted(epics_dir.glob("*.md")):
        lines = f.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            m = ID_RE.search(line) if line.startswith("### ") else None
            if not m:
                continue
            for j in range(i + 1, min(i + 12, len(lines) - 2)):
                if lines[j].startswith("| Người"):
                    head = [c.strip() for c in lines[j].strip().strip("|").split("|")]
                    vals = [c.strip() for c in lines[j + 2].strip().strip("|").split("|")]
                    cards[m.group(1)] = dict(zip(head, vals, strict=False)) | {"file": f.name}
                    break
    return cards


def compare_card(t: Task, card: dict[str, str]) -> list[str]:
    """Trả về danh sách điểm lệch giữa backlog và task card."""
    diffs = []
    if parse_roles(card.get("Người", "")) != t.roles:
        diffs.append(f"vai trò {card.get('Người')!r} ≠ backlog {t.roles}")
    try:
        if abs(float(card.get("Ước lượng", "0").replace(",", ".")) - t.days) > 1e-9:
            diffs.append(f"ước lượng {card.get('Ước lượng')} ≠ backlog {fmt(t.days)}")
    except ValueError:
        diffs.append(f"ước lượng không đọc được: {card.get('Ước lượng')!r}")
    try:
        if parse_sprints(card.get("Sprint", "")) != t.sprints:
            diffs.append(f"sprint {card.get('Sprint')!r} ≠ backlog {'/'.join(t.sprints)}")
    except ValueError:
        diffs.append(f"sprint không đọc được: {card.get('Sprint')!r}")
    if card.get("Ưu tiên", "").strip() != t.priority.strip():
        diffs.append(f"ưu tiên {card.get('Ưu tiên')!r} ≠ backlog {t.priority!r}")
    if set(ID_RE.findall(card.get("Phụ thuộc", ""))) != set(t.deps):
        diffs.append(f"phụ thuộc {card.get('Phụ thuộc')!r} ≠ backlog {', '.join(t.deps) or '—'}")
    return diffs


def find_cycles(tasks: dict[str, Task]) -> list[list[str]]:
    color: dict[str, int] = {}
    stack: list[str] = []
    cycles: list[list[str]] = []

    def visit(n: str) -> None:
        color[n] = 1
        stack.append(n)
        for d in tasks[n].deps:
            if d not in tasks:
                continue
            if color.get(d) == 1:
                cycles.append(stack[stack.index(d) :] + [d])
            elif color.get(d) is None:
                visit(d)
        stack.pop()
        color[n] = 2

    for n in tasks:
        if color.get(n) is None:
            visit(n)
    return cycles


def critical_path(tasks: dict[str, Task]) -> tuple[float, list[str]]:
    memo: dict[str, tuple[float, list[str]]] = {}

    def longest(n: str) -> tuple[float, list[str]]:
        if n in memo:
            return memo[n]
        best = (0.0, [])
        for d in tasks[n].deps:
            if d in tasks:
                cand = longest(d)
                if cand[0] > best[0]:
                    best = cand
        memo[n] = (best[0] + tasks[n].days, best[1] + [n])
        return memo[n]

    return max((longest(n) for n in tasks), key=lambda x: x[0], default=(0.0, []))


def near_critical(tasks: dict[str, Task], ratio: float = 0.85) -> list[tuple[float, list[str]]]:
    """Mọi chuỗi kết thúc ở task 'lá' (không ai phụ thuộc) dài >= ratio × chuỗi dài nhất."""
    memo: dict[str, tuple[float, list[str]]] = {}

    def longest(n: str) -> tuple[float, list[str]]:
        if n not in memo:
            best = max(
                (longest(d) for d in tasks[n].deps if d in tasks),
                key=lambda x: x[0],
                default=(0.0, []),
            )
            memo[n] = (best[0] + tasks[n].days, best[1] + [n])
        return memo[n]

    used = {d for t in tasks.values() for d in t.deps}
    chains = sorted((longest(n) for n in tasks if n not in used), key=lambda x: -x[0])
    top = chains[0][0] if chains else 0.0
    # Với mỗi task lá, cũng xét chuỗi dài nhất đi qua từng task (để không bỏ sót nhánh song song)
    for n in tasks:
        length, path = longest(n)
        if length >= ratio * top and all(path != c[1] for c in chains):
            chains.append((length, path))
    keep = [c for c in chains if c[0] >= ratio * top]
    # bỏ chuỗi là tiền tố của chuỗi khác
    result = []
    for c in sorted(keep, key=lambda x: -x[0]):
        if not any(c[1] == o[1][: len(c[1])] and c is not o for o in keep):
            result.append(c)
    return result


def load_table(tasks: list[Task]) -> dict[str, dict[str, float]]:
    load: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for t in tasks:
        if t.status in ("cut", "done") or not t.roles:
            continue
        share = t.days / len(t.roles) / len(t.sprints)
        for r in t.roles:
            for s in t.sprints:
                load[r][s] += share
    return load


def fmt(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def report(
    tasks: list[Task], util: float, board_only: bool = False, show_notes: bool = False
) -> int:
    by_id = {t.id: t for t in tasks}
    errors: list[str] = []
    warnings: list[str] = []
    notes: list[str] = []

    # Bảng trạng thái
    status_count: dict[str, int] = defaultdict(int)
    for t in tasks:
        status_count[t.status] += 1
    total_days = sum(t.days for t in tasks if t.status != "cut")
    done_days = sum(t.days for t in tasks if t.status == "done")
    print("== BẢNG TRẠNG THÁI ==")
    print(
        f"{len(tasks)} task · "
        + " · ".join(f"{k}: {v}" for k, v in sorted(status_count.items()))
        + f" · đã xong {fmt(done_days)}/{fmt(total_days)} ngày công"
    )
    for st in ("doing", "review", "blocked"):
        items = [t for t in tasks if t.status == st]
        if items:
            print(f"  {st}: " + ", ".join(f"{t.id} ({t.owner or '?'})" for t in items))
    ready = [
        t.id
        for t in tasks
        if t.status == "todo" and all(by_id.get(d) and by_id[d].status == "done" for d in t.deps)
    ]
    print("  Sẵn sàng làm (phụ thuộc đã xong): " + (", ".join(ready) or "—"))
    if board_only:
        return 0

    # 1–2. Phụ thuộc
    for t in tasks:
        for d in t.deps:
            if d not in by_id:
                errors.append(f"{t.id}: phụ thuộc {d} không tồn tại (dòng {t.line})")
    for c in find_cycles(by_id):
        errors.append("Vòng lặp phụ thuộc: " + " → ".join(c))

    # 3. Thứ tự sprint
    for t in tasks:
        for d in t.deps:
            dep = by_id.get(d)
            if not dep:
                continue
            if dep.start > t.end:
                errors.append(
                    f"{t.id} ({'/'.join(t.sprints)}) phụ thuộc {d} ({'/'.join(dep.sprints)}) "
                    "nhưng task phụ thuộc bắt đầu SAU khi task này kết thúc"
                )
            elif dep.end > t.start:
                notes.append(
                    f"{t.id} ({'/'.join(t.sprints)}) phụ thuộc {d} ({'/'.join(dep.sprints)}): "
                    "cùng sprint — phải xong trước"
                )

    # 4. Task card
    cards = card_ids()
    for t in tasks:
        if t.id not in cards:
            errors.append(f"{t.id}: chưa có task card trong docs/plan/epics/")
    for cid in sorted(cards - set(by_id)):
        errors.append(f"{cid}: có task card nhưng không có trong backlog.md")
    headers = card_headers()
    for t in tasks:
        if t.id in cards and t.id not in headers:
            errors.append(f"{t.id}: task card thiếu bảng 'Người | Ước lượng | Sprint | …'")
        elif t.id in headers:
            for d in compare_card(t, headers[t.id]):
                errors.append(f"{t.id}: backlog và task card ({headers[t.id]['file']}) lệch — {d}")

    # 5. Tải công việc
    load = load_table(tasks)
    print(f"\n== TẢI CÔNG VIỆC (ngày công) — sức chứa = số ngày × {fmt(util)} ==")
    print(
        "Vai trò | "
        + " | ".join(f"{s} (≤{fmt(SPRINT_DAYS[s] * util)})" for s in SPRINTS)
        + " | Tổng"
    )
    for role in sorted(load):
        cells = []
        for s in SPRINTS:
            v = load[role].get(s, 0.0)
            cap = SPRINT_DAYS[s] * util
            mark = " ⚠" if v > cap + 1e-9 else ""
            if mark:
                warnings.append(f"{role} quá tải ở {s}: {fmt(v)} > {fmt(cap)} ngày công")
            cells.append(f"{fmt(v)}{mark}")
        print(
            f"{role:7} | "
            + " | ".join(f"{c:>9}" for c in cells)
            + f" | {fmt(sum(load[role].values()))}"
        )

    # 6. Đường găng
    length, path = critical_path(by_id)
    print(f"\n== ĐƯỜNG GĂNG (chuỗi phụ thuộc dài nhất): {fmt(length)} ngày công ==")
    print("  " + " → ".join(path))
    chains = near_critical(by_id)
    print(f"  Chuỗi gần găng (≥ 85% = {fmt(0.85 * length)} ngày công):")
    for c_len, c_path in chains:
        print(f"   {fmt(c_len):>5} · " + " → ".join(c_path))
    on_critical = {n for _, p in chains for n in p}
    not_starred = sorted(n for n in on_critical if not by_id[n].starred)
    if not_starred:
        warnings.append(
            "Task trên chuỗi găng/gần găng nhưng chưa đánh dấu ★: " + ", ".join(not_starred)
        )
    extra_star = sorted(t.id for t in tasks if t.starred and t.id not in on_critical)
    if extra_star:
        notes.append("Đánh dấu ★ nhưng không còn trên chuỗi găng: " + ", ".join(extra_star))

    print("\n== KẾT QUẢ KIỂM TRA ==")
    for e in errors:
        print("  LỖI    " + e)
    for w in warnings:
        print("  CẢNH BÁO " + w)
    if notes:
        print(f"  ({len(notes)} cặp task phụ thuộc nằm cùng sprint — xem bằng --notes)")
    if show_notes:
        for n in notes:
            print("  LƯU Ý  " + n)
    if not errors and not warnings:
        print("  Không có lỗi hay cảnh báo.")
    print(f"\n{len(errors)} lỗi, {len(warnings)} cảnh báo.")
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--util", type=float, default=0.7, help="tỷ lệ thời gian dành cho dự án (mặc định 0.7)"
    )
    ap.add_argument("--board", action="store_true", help="chỉ in bảng trạng thái")
    ap.add_argument("--notes", action="store_true", help="in cả các cặp phụ thuộc cùng sprint")
    # Before parse_args: --help and errors print Vietnamese text (cp1252 console on Windows).
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = ap.parse_args(argv)
    return report(parse_backlog(), args.util, args.board, args.notes)


if __name__ == "__main__":
    raise SystemExit(main())
