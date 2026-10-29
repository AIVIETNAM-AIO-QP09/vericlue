# Bàn giao · IOS-02 · Lý Anh Quân+Codex · 2026-10-28 04:01

**Nhánh:** `feat/IOS-02-android-alignment`
**Trạng thái task sau phiên này:** `doing` — chỉ chặng 0 hoàn tất; receipt và luồng/UI chưa triển khai.

## Đã xong
- Kiểm worktree sạch, tạo nhánh riêng từ `6aef3acadb3fca994c046b0ee079d02162958520` (IOS-06); không stash/checkout main hoặc merge Android.
- Khóa Android tham chiếu `feat/APP-01-account-flow` tại `f034fa9406ea9aef1ee86365ce82142de517d553`.
- Xác nhận project.pbxproj trên đĩa và baseline cùng blob `3757f703fa286597f132a254105c3ace82decb68`, giữ ngoại lệ Info.plist đã khôi phục.
- Viết `apps/ios/docs/android-alignment.md`: bảng màn/route, ba purpose, nguồn receipt contract, lệch backend và thứ tự triển khai/PR. Cập nhật liên kết ở plan/task card và dòng IOS-02 backlog, không tạo mã task mới.
- Ghi quyết định sếp: recovery bỏ CCCD; receipt riêng trước; không gộp ký media/device proof. Không lưu mô tả PR bằng file md.

## Đang dở
- Chặng 1 receipt chưa bắt đầu. Local contracts/API baseline chưa có receipt/account endpoint; nguồn mới có ở commit Android đã khóa. Không sửa contracts/backend để che khác biệt; chưa thể nghiệm thu receipt thật với API mock cũ.
- Luồng gọn, auto CCCD, payload chờ confirm và theme vẫn chưa được triển khai. Chưa có bằng chứng build/test mới, chưa commit/push/PR.

## Bước tiếp theo
1. Theo yêu cầu tiếp theo của sếp, làm receipt riêng theo nguồn contract đã khóa; xác định kho lưu iOS, thêm test MockURLProtocol/storage, không tạo hoặc giả lập khóa ký.
2. Nếu cần nghiệm thu backend thật, phối hợp tích hợp phiên bản hỗ trợ account/receipt ở bước riêng; không merge main hoặc sửa schema/backend ngầm trong task client.
3. Build sau chặng triển khai; chỉ chạy test khi sếp yêu cầu. Sau receipt mới làm route/CCCD, giữ video chờ confirm và theme theo tài liệu đối chiếu.

## Quyết định, lưu ý, bẫy
- Không dùng receipt thay cho thông tin xác thực; không tuyên bố reauth thật hoạt động khi backend chặn 503/thiếu device proof.
- Đọc source bằng git show/git grep. Skill codebase-memory được dùng nhưng graph chưa index; check_index_coverage báo không có project, nên không tuyên bố graph bao phủ đầy đủ.
- Trạng thái test 105/105 là lịch sử IOS-06, không phải kết quả chạy trên chức năng mới.

## Câu hỏi cho nhóm
- Backend/contract receipt mới chưa có trên nhánh iOS nền: thống nhất môi trường tích hợp trước nghiệm thu receipt thật.
- Recovery bỏ CCCD đã được sếp chọn theo tài liệu, nhưng Android source tại f034fa9 vẫn vào CCCD; báo Quang để hai phía thống nhất, không quay lại sao chép code mâu thuẫn.
- Kho lưu receipt iOS cụ thể chốt trong chặng 1; không đồng nghĩa thêm khóa thiết bị vào scope.

## Kiểm tra

- Chưa build hoặc chạy test, đúng phạm vi chặng 0.
- git status sạch trước tạo nhánh; git rev-parse/git hash-object xác nhận hai baseline và project như trên.
- `git diff --check`: sạch. Hooks áp dụng trên năm file tài liệu Passed; hook không có loại file phù hợp Skipped. `uv run python scripts/plan_check.py`: exit 0, 0 lỗi/10 cảnh báo tải công việc/đường găng.
- `git diff --name-only` theo phạm vi source Swift/project/contracts/backend/ADR/STATUS: không có thay đổi. Chỉ có năm file tài liệu mới/sửa, không có staged files hoặc commit mới.
