"""Package actual Compose renders for local review; no real personal data."""

import argparse
import hashlib
import html
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, help="Output folder for gallery and PNGs")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
images = root / "apps/android/app/src/test/snapshots/images"
destination = args.output or root / "tmp/vericlue-ui-review"
destination.mkdir(parents=True, exist_ok=True)
labels = {
    "00_host": "Ứng dụng tích hợp (minh họa)",
    "01_splash": "Mở VeriClue",
    "02_auth": "Bắt đầu xác minh",
    "03_terms": "Đồng ý xác minh",
    "03b_terms_selected": "Sau khi chọn đồng ý",
    "04_phone": "Nhập số điện thoại",
    "05_otp": "Nhập mã xác nhận",
    "06_card_front": "Quét mặt có chân dung",
    "07_card_processing": "Đọc thông tin thẻ",
    "08_confirm": "Xác nhận thông tin",
    "09_face_ready": "Chuẩn bị xác minh khuôn mặt",
    "10_face_framing": "Đưa mặt vào khung",
    "11_face_still": "Giữ đầu yên",
    "12_face_colour": "Thử thách ánh sáng",
    "13_face_gaze": "Nhìn theo chấm sáng",
    "14_face_left": "Quay sang trái",
    "15_face_right": "Quay sang phải",
    "16_face_front": "Nhìn thẳng",
    "17_checking": "Kiểm tra kết quả",
    "18_success": "Xác minh thành công",
    "b01_terms_details": "Thông tin đồng ý mở rộng",
    "b02_card_back": "Quét thêm mặt có QR khi cần",
    "b03_voice": "Đọc câu xác nhận khi được yêu cầu",
    "b04_voice_recording": "Đang ghi âm",
    "b05_edit": "Chỉnh sửa thông tin",
    "b06_card_ready": "Đã nhận đủ QR và chân dung (minh họa)",
    "b07_success_voice": "Thành công sau nhánh giọng nói (minh họa)",
    "e01_otp_error": "Mã xác nhận chưa đúng",
    "e02_card_timeout": "Quét thẻ quá lâu",
    "e03_card_retry": "Cần quét lại thẻ",
    "e04_review": "Chưa hoàn tất xác minh",
    "e05_network": "Mất kết nối",
    "e06_card_glare": "Điều chỉnh thẻ bị lóa",
}
classes = {
    "OnboardingJourneySnapshotTest": ("normal", "Kích thước điện thoại tiêu chuẩn"),
    "CompactOnboardingJourneySnapshotTest": ("compact", "Màn hình 375 dp"),
    "LargeTextOnboardingJourneySnapshotTest": ("large-text", "Chữ hệ thống 200% trên màn 375 dp"),
    "LandscapeOnboardingJourneySnapshotTest": (
        "landscape",
        "Kiểm tra bố cục ngang — app vẫn khóa dọc",
    ),
}
records = []
for source in sorted(images.glob("*.png")):
    for class_name, (group, _) in classes.items():
        marker = "_" + class_name + "_"
        if marker not in source.stem:
            continue
        suffix = source.stem.split(marker, 1)[1].split("_", 1)[1]
        code, theme = suffix.rsplit("_", 1)
        if code not in labels or theme not in ("light", "dark"):
            raise ValueError("Unrecognized render: " + source.name)
        folder = destination / group / theme
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / (code + ".png")
        shutil.copy2(source, target)
        records.append(
            {
                "group": group,
                "theme": theme,
                "code": code,
                "label": labels[code],
                "file": target.relative_to(destination).as_posix(),
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            }
        )
        break
for group in ("normal", "compact", "large-text", "landscape"):
    for theme in ("light", "dark"):
        expected = len(labels) if group == "normal" else 14
        if len([r for r in records if r["group"] == group and r["theme"] == theme]) != expected:
            raise RuntimeError(f"Incomplete renders for {group}/{theme}; no gallery published")

sections = []
for group, title in classes.values():
    for theme, theme_title in [("light", "Giao diện sáng"), ("dark", "Giao diện tối")]:
        rows = [r for r in records if r["group"] == group and r["theme"] == theme]
        for prefix, category in [
            ("main", "Luồng chính"),
            ("b", "Nhánh chỉ xuất hiện khi cần"),
            ("e", "Lỗi và hướng xử lý"),
        ]:
            selected = [
                r
                for r in rows
                if (r["code"][0].isdigit() if prefix == "main" else r["code"].startswith(prefix))
            ]
            if not selected:
                continue
            cards = "".join(
                '<figure><a href="{0}" target="_blank"><img src="{0}" loading="lazy" alt="{1}"></a><figcaption>{2} · {1}</figcaption></figure>'.format(
                    html.escape(r["file"]), html.escape(r["label"]), html.escape(r["code"])
                )
                for r in sorted(selected, key=lambda r: r["code"])
            )
            sections.append(
                "<details"
                + (" open" if group == "normal" and theme == "light" else "")
                + "><summary>"
                + html.escape(title + " · " + theme_title + " · " + category)
                + '</summary><div class="grid">'
                + cards
                + "</div></details>"
            )

page = (
    """<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>VeriClue — Giao diện sau cập nhật</title><style>
body{font:16px/1.6 system-ui,sans-serif;margin:0;background:#f1f5f9;color:#172033}main{max-width:1300px;margin:auto;padding:28px}h1{font-size:28px;margin:0}p{max-width:85ch}details{background:white;border-radius:16px;margin:20px 0;padding:20px}summary{cursor:pointer;font-weight:650}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:24px;padding-top:20px}figure{margin:0}img{display:block;width:100%;max-width:400px;height:auto;border:1px solid #e2e8f0;border-radius:16px}figcaption{padding-top:10px;font-weight:600}a{color:#174c91}code{font-size:13px}
</style><main><h1>VeriClue — Giao diện sau cập nhật</h1><p>Ảnh render trực tiếp từ màn hình Jetpack Compose đã cập nhật, theo thứ tự luồng người dùng mới. Bấm ảnh để xem kích thước gốc. Các ảnh camera, thông tin cá nhân và mã xác nhận đều là minh họa; không phải kết quả kiểm thử camera, AI hay dữ liệu thật trên điện thoại.</p><p>Quét mặt có chân dung trước; chỉ yêu cầu thêm mặt có QR khi chưa đọc được. Đọc câu xác nhận là nhánh bổ sung, không phải bước bắt buộc cho mọi phiên. Các ảnh quay trái/phải minh họa một thứ tự thử thách; thứ tự thật do máy chủ quyết định.</p>"""
    + "".join(sections)
    + "</main></html>"
)
(destination / "index.html").write_text(page, encoding="utf-8")
ui_files = sorted((root / "apps/android/app/src/main").rglob("*.kt"))
digest = hashlib.sha256()
for file in ui_files:
    digest.update(file.relative_to(root).as_posix().encode())
    digest.update(file.read_bytes())
manifest = {
    "source_commit": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip(),
    "ui_has_uncommitted_changes": subprocess.run(
        ["git", "diff", "--quiet", "--", "apps/android/app/src/main"], cwd=root
    ).returncode
    != 0,
    "ui_kotlin_sha256": digest.hexdigest(),
    "renderer": "Paparazzi 1.3.5 / actual Compose",
    "synthetic_data_only": True,
    "images": records,
}
(destination / "manifest.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
)
archive = destination.with_suffix(".zip")
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
    for file in sorted(destination.rglob("*")):
        if file.is_file():
            bundle.write(file, file.relative_to(destination))
print(
    json.dumps(
        {"gallery": str(destination / "index.html"), "zip": str(archive), "images": len(records)},
        ensure_ascii=False,
    )
)
