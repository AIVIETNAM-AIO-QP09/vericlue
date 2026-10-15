"""Câu tiếng Việt tự soạn cho VOICE-04, không dùng transcript của dữ liệu đánh giá."""

from __future__ import annotations

import random
import secrets

PROMPTS: tuple[str, ...] = (
    "Buổi sáng mẹ vẫn mở cửa nhà cho em",
    "Chiều nay bé giữ rổ cá ở cạnh sân",
    "Mẹ nhờ em giữ đôi đũa ở cạnh chén sứ",
    "Những bông hoa đỏ nở cạnh đường lúc sáng",
    "Trưa nay mẹ nhắc em rửa những chiếc bát rồi",
    "Chị mở cửa sổ cho những làn gió mát",
    "Bé giữ khăn sạch để bà lau chiếc bàn",
    "Những quả cam chín nằm cạnh giỏ rau xanh",
    "Em vẫn ngồi đợi mẹ ở giữa sân nắng",
    "Bà bảo em giữ lại những chiếc lá xanh",
    "Buổi chiều chị dẫn em ra chợ lấy sữa",
    "Những tiếng chim hót làm mẹ mở cửa sớm",
    "Ông vẫn nhắc cháu rửa mặt trước bữa chiều",
    "Chú giữ những quả bóng cạnh hàng rào xanh",
    "Mẹ mở chiếc tủ gỗ rồi lấy khăn cho em",
    "Bé vẫn giúp mẹ rửa những quả cà cho em",
    "Chiều về mẹ cất đũa rồi mở cửa bếp cho em",
    "Những giọt mưa nhỏ rơi xuống chiếc bàn gỗ",
    "Chị bảo em để những quả táo cạnh bình",
    "Em giữ rổ trứng để mẹ nấu bữa chiều",
    "Buổi sáng bà vẫn gọi em dậy đúng giờ",
    "Mẹ để những chiếc áo sạch gần cửa sổ cho em",
    "Trẻ nhỏ vẫn thích nghe bà kể chuyện xưa",
    "Buổi sáng chị dẫn hai em đi giữa hàng cây",
)


def generate_prompt(previous: str | None = None, *, rng: random.Random | None = None) -> str:
    """Chọn câu mới bằng nguồn ngẫu nhiên hệ thống; rng chỉ dành cho test tái lập."""
    candidates = tuple(prompt for prompt in PROMPTS if prompt != previous)
    return secrets.choice(candidates) if rng is None else rng.choice(candidates)
