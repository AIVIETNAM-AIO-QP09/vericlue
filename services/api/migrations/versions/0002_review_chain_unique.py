"""Ràng buộc UNIQUE(case_id, prev_hash) trên review_events (REV-01).

Mỗi sự kiện của một ca phải nối vào một `prev_hash` duy nhất (sự kiện đầu dùng hash genesis
64 số 0), nên hai ghi đồng thời không thể cùng nối vào một điểm: chuỗi không thể rẽ nhánh ở tầng DB.
Dùng unique index (không dùng batch_alter_table) để SQLite không dựng lại bảng và làm mất trigger
chỉ-ghi-thêm. Chuỗi hợp lệ cũ không vi phạm ràng buộc; chuỗi đã rẽ nhánh sẽ làm upgrade lỗi (đúng ý).
"""

from alembic import op

revision = "0002_review_chain_unique"
down_revision = "0001_storage"
branch_labels = None
depends_on = None

INDEX = "uq_review_events_case_prev_hash"


def upgrade() -> None:
    op.create_index(INDEX, "review_events", ["case_id", "prev_hash"], unique=True)


def downgrade() -> None:
    op.drop_index(INDEX, table_name="review_events")
