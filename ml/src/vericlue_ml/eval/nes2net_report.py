"""Vietnamese text for internal per-window diagnostics; no scores for citizens."""

from vericlue_ml.voice.nes2net_timeline import WINDOWS


def timeline_text(payload: dict) -> str:
    """Render measured coverage separately from model correctness or a verdict."""
    result = payload["result"]
    quality = result.get("quality", {})
    rows = next(
        (item["value"] for item in result.get("evidence", []) if item["name"] == WINDOWS), []
    )
    text = "CHƯA KẾT LUẬN GIỌNG THẬT / GIẢ"
    if not rows:
        text += "\nChưa kiểm được các đoạn; thử lại hoặc kiểm tra worker/runtime."
    else:
        text += (
            f"\nĐã đo {int(quality['measured_windows'])}/{len(rows)} đoạn."
            f" Phủ {quality['measured_seconds']:.2f}/{quality['input_seconds']:.2f} giây gốc"
            " (không cộng trùng)."
        )
        text += "\nCác đoạn trên bản thu gốc:"
        for row in rows:
            measured = row["result"]
            text += f"\n{row['start_s']:.2f} → {row['end_s']:.2f} s: "
            if measured["status"] == "degraded":
                text += f"điểm {measured['score']:.4f} · chỉ tham khảo"
            elif measured["status"] == "not_applicable":
                text += "chưa đo · thiếu tiếng nói (cổng VAD)"
            else:
                text += f"chưa đo · lỗi {measured.get('error_code') or 'E_INTERNAL'}"
        if not quality["all_source_samples_measured"]:
            text += "\nCòn vùng chưa đo; không xem toàn bản thu là đã được kiểm."
        if quality["repeated_to_four_seconds"]:
            text += "\nBản thu ngắn hơn 4 giây: lặp mẫu để đủ đầu vào, không tăng thời gian gốc."
        text += (
            "\n\nĐộ phủ chỉ cho biết phần đã chạy mô hình, không phải độ chính xác."
            "\nĐiểm giả − thật cao hơn nghiêng về giả trong mô hình; không phải xác suất."
            "\nKhông gộp các điểm thành kết luận cho toàn bản thu."
        )
    return (
        text + "\n\nChưa xác minh tương đương bản gốc hoặc hiệu chỉnh cho tiếng Việt."
        f"\nTrạng thái kỹ thuật: {result['status']} / {result['gate']}"
        f"\nMã lý do: {result.get('error_code') or 'không'}"
        f"\nThời gian worker/trao đổi: {payload.get('round_trip_ms', 0) / 1000:.2f} giây"
    )
