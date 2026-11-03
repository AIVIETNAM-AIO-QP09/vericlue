# Bàn giao · APP-03 · Ngoc Quang+Codex · 2026-11-03 07:57

**Nhánh:** `codex/APP-11-s24fe-integration`
**Trạng thái:** `doing` — sửa đúng tiền xử lý GenD, chưa nghiệm thu khôi phục.

## Đã xong
- Lượt khôi phục 07:39 ngày03/11 bị GenD chặn trước màn giọng. Sáu mô-đun
  mặt còn lại đạt, đủ ba view và cùng video, đúng policy; tài khoản giữ nguyên.
  Không dùng lượt này để chọn model, crop, dtype, offset hoặc ngưỡng.
- Đối chiếu upstream MIT `yermandy/GenD` commit
  `387a42266dd385fbe8f7626c5d3aa03eea3bfaab` phát hiện sai lệch căn mặt:
  upstream giữ `np.int64` từ `.astype(int)`, wrapper đổi thành Python `int`.
  Trên NumPy2.5.4, scalar promotion làm tròn đích khác, dẫn đến ma trận và
  pixel khác. Sáu trường hợp tổng hợp cố định: trước sửa4/6 khác, sai lệch
  pixel tối đa8; CLIPImageProcessor so với `to_tensor` khớp cả6 trường hợp.
- Sửa đúng kiểu số; không đổi công thức, scale1.3, model, lớp softmax hoặc
  ngưỡng. Thêm `align-upstream-numpy-v2` vào mọi version GenD; calibrator cũ
  không tự gắn vào pipeline mới. Cập nhật khai báo phiên bản notebook/diagnostic,
  sinh lại notebook bằng builder. Không sửa thresholds.yaml hoặc artifact cũ.
- Thêm `ml/scripts/parity_gend.py` và README: chạy mã gốc độc lập, kiểm SHA,
  nạp strict394 tensor, 9 input tổng hợp, batch1/2/9; so pooled features,
  normalized features, logits, hai xác suất và xác suất lớp1. CPU/FP32,
  atol=rtol=1e-5 đã khóa trước. Dữ liệu thiếu/lỗi là UNVERIFIED, sai khác FAIL.
- Baseline classifier thật:15 kiểm tra số học đạt, sai lệch lớn nhất
  5.960464477539063e-8. Toàn pipeline baseline vẫn FAIL vì bước căn mặt;
  không dùng classifier pass để che lỗi preprocessing.
- Replay ngoại tuyến trên đúng một video sáng nay, ba view theo timestamp
  đã xác minh: upstream SCRFD box/landmark khớp3/3; ảnh căn/tensor khác ở
  front/right, left khớp. Cùng tensor thì logits khớp. **Cả mã gốc và wrapper
  cũ đều từ chối front theo ngưỡng hiện có**; sửa alignment không đồng nghĩa
  giải quyết toàn bộ từ chối người thật. DB chỉ đọc, lease đã release, media
  gốc giữ nguyên; không công khai điểm, ID, transcript hoặc ảnh/video.

## Đang dở
- Parity đầy đủ sau sửa và toàn bộ test Python không slow đã PASS. API mới
  đã triển khai và server sẵn sàng; chi tiết bằng chứng ở mục cuối.
- Khôi phục/giọng/lipsync trên điện thoại chưa nghiệm thu. Cần dữ liệu có
  quyền dùng, tách người/nguồn để hiệu chỉnh/đánh giá đúng phiên bản mới.

## Bước tiếp theo
1. Theo dõi CI đúng HEAD của Draft PR135; không merge khi nghiệm thu còn mở.
2. Chuẩn bị dữ liệu hiệu chỉnh/đánh giá đúng version, tách người/nguồn.
3. Nghiệm thu lại khi có căn cứ; không yêu cầu thử lặp lại để tìm ngưỡng đạt.

## Quyết định, lưu ý, bẫy
- Hai agent độc lập dựng/review oracle; agent khác đưa công cụ vào repo,
  có test thiếu bằng chứng, NaN, shape, inventory, polarity và nguồn lệch.
- Kết luận cũ trong bàn giao02/11-0949 rằng ảnh tổng hợp khớp chỉ đúng bộ
  đầu vào từng thử; bộ hình học rộng hơn lần này đã tìm được sai lệch. Không
  dùng kết quả cũ như chứng minh parity chung.
- Baseline nguồn8c40fd0/fb8c2bf. Mã sửa trong working tree có hash riêng và
  `repo_dirty=true`; không gán phép đo trước commit cho một HEAD sạch giả.
- Vùng riêng: `D:/vericlue/tmp/gend-parity-2026-11-03` và
  `D:/vericlue/tmp/gend-phone-parity-2026-11-03`. Không commit upstream source,
  trọng số hoặc báo cáo có điểm người thử. Script public chỉ dùng tổng hợp.

## Câu hỏi cho nhóm
- Sau sửa parity, vẫn thiếu bằng chứng hiệu chỉnh chống từ chối người thật.
  Nhóm cần chuẩn bị dữ liệu theo capture/version này; không lấy mẫu nghiệm
  thu điện thoại hoặc VIVOS32 parity làm fit, không ép degraded/error thành pass.

## Test đã chạy
- Alignment/version RED7 lỗi,2 đạt → GREEN9 đạt. Nhóm GenD gồm5 file:
  **105 đạt,2 bỏ qua**. Calibrator cũ được kiểm phải bị từ chối ở version mới.
- Khai báo version hiệu chỉnh: RED1 lỗi đúng version cũ → toàn file14 đạt.
- Công cụ parity: **25 test không model đạt**; review độc lập đã sửa ca báo
  cáo preprocessing thiếu trường nhưng có thể được coi là pass.
- Nhóm API manual-demo/calibration/dynamic flows và notebook builder: không lỗi.
- Ruff check/format toàn repo sạch; notebook builder --check đạt.
- Toàn bộ Python không slow: **5364 đạt, 92 bỏ qua, 25 deselected**, 0 lỗi,
  2 cảnh báo serializer; 839,59 giây. Dùng PYTHONPATH tuyệt đối vào checkout này.
- Helper triển khai API riêng có **32 test đạt**, review độc lập không thấy
  blocker; kiểm hash nguồn/trọng số/runtime, toàn bộ hàng SQLite, khóa/media,
  APK và cấu hình trước/sau. Chưa tính đây là bằng chứng server đã triển khai.
- Ruff check sạch, format 932 file không cần đổi; plan_check 0 lỗi, 10 cảnh
  báo tải/phụ thuộc có sẵn. Review cuối mã và bằng chứng không còn blocker.

## Đối chứng sau sửa đã hoàn tất

- Công cụ trong repo chạy với trọng số thật:6/6 alignment khớp từng pixel,
  6/6 processor tensor sai lệch0; 15 kiểm tra classifier đạt, max abs
  5.960464477539063e-8. Có9 input tổng hợp riêng biệt,12 lượt forward/backend
  qua batch1/2/9; không cộng thành12 mẫu độc lập. Nguồn/runtime/model không đổi.
- Replay cùng video cũ:3/3 view khớp box, landmark, ảnh căn và tensor; logits
  cùng input và toàn pipeline đều khớp theo tolerance đã khóa. Lease đã
  release, media/cấu hình giữ nguyên. Cả original/fixed vẫn chặn front theo
  cutoff hiện có. Không chuyển kết quả DB cũ thành pass hoặc tuyên bố nghiệm thu.
- [Báo cáo aggregate](../results/APP-03-gend-parity-2026-11-03.json) ghi hash
  mã đã đo, model/runtime và mẫu số; giữ điểm người thử ở vùng riêng.

## Triển khai thực tế lúc 08:17 ngày 03/11

- Commit mã: `f3305b2c150c062a6c5b685a81b590b18342426c`, đã push PR135.
  API chạy từ Git archive bất biến gồm 611 file; hash mã GenD/công cụ/helper
  khớp bằng chứng native trước commit. Commit bàn giao sau đó chỉ đổi tài liệu.
- Chuẩn bị, kiểm tra và kích hoạt API riêng bằng helper đã review. Backup tại
  `revision-backups/before-api-only-gend-f3305b2c150c` trong bundle riêng.
  Toàn bộ hàng SQLite, khóa/media, APK và profile khớp trước/sau kích hoạt;
  không migration hoặc sửa quyết định cũ. APK giữ nguồn `c646868`.
- Server thực tế báo READY; health `ok`, `failed_modules=[]`, xác minh đúng
  instance bằng phiên ký mới và đúng policy. Cờ health `mock_models=true`
  phản ánh mặc định toàn API, không thay thế kiểm cấu hình/worker của phiên
  manual demo chạy mô hình thật. Selector Qwen1.7B và sáu ngưỡng giữ nguyên.
- S24 FE vẫn kết nối ADB; reverse cổng8421 được đặt và kiểm lại. Không cài
  APK, tự mở app hoặc tạo lượt xác minh người thật trong bước triển khai này.
- Máy/server giữ bật cho người dùng. Không tiếp tục lệnh tắt máy qua đêm cũ.
- Khôi phục vẫn **chưa nghiệm thu**: parity đã sửa đúng, nhưng original/fixed
  cùng từ chối video cố định ở ngưỡng hiện có. Cần hiệu chỉnh độc lập đúng version.

## Lượt người dùng sau triển khai: mặt đạt nhưng hết hạn

- Lượt khôi phục 08:21 có cả 7 mô-đun mặt `ok/pass`, gồm GenD đúng version
  mới. Kết quả cuối vẫn `review`, chưa yêu cầu giọng, tài khoản giữ nguyên.
- Đối chiếu thời điểm: quyết định lúc 08:23:15,416, thử thách hết hạn lúc
  08:23:11,111; xử lý vượt deadline khoảng 4,305 giây. Token vẫn còn khoảng
  175,695 giây. Dựng lại các gate từ snapshot chỉ đọc với đúng profile `mvp`:
  nếu còn hạn, manual gate đạt và route/identity đều trả `voice_challenge`.
  Đây là lỗi thiếu thời gian của cấu hình demo CPU, không phải lượt GenD fail.
- Chỉ profile demo riêng được đổi `CHALLENGE_TTL_SECONDS=180` thay mặc định
  120; không đổi mặc định trong repo. Áp dụng cho thử thách mặt và giọng/reread
  được phát hành sau đó; token300/max900, giới hạn bản thu và sáu ngưỡng giữ
  nguyên. Giữ mọi kiểm tra hết hạn trước/sau suy luận. Lượt cũ vẫn đóng,
  không sửa quyết định hoặc gia hạn challenge đã phát hành.
- Helper riêng được review trước chạy; kiểm đúng một trường Settings thay
  đổi, backup `.env`/build-info tại
  `revision-backups/before-cpu-demo-ttl180-20261103`. Sau kích hoạt, mọi hàng
  SQLite, khóa/media, nguồn API và APK giữ nguyên; cập nhật hash profile.
- Thêm 7 ca hồi quy: hết hạn trong nhóm mặt hoặc face-match dù cả7 đạt;
  cùng thời gian xử lý với challenge mới180 chuyển sang giọng; profile mới
  không hồi sinh challenge120 đã hết hạn; token vẫn là giới hạn độc lập.
  Bốn file liên quan **703 đạt**, 1 cảnh báo Starlette/httpx có sẵn; Ruff sạch,
  review độc lập không có blocker. Đây là test logic với detector tổng hợp,
  không phải nghiệm thu điện thoại. Không cần chạy lại native parity vì mã
  suy luận/model không đổi.
- Commit GenD `f3305b2` và commit bàn giao `68637fa` đều có toàn bộ CI thành
  công; riêng HEAD `68637fa` đã kiểm đủ10/10. PR135 tiếp tục draft, chưa merge.
