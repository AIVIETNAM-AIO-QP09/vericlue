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
- Parity đầy đủ sau sửa và toàn bộ test Python không slow đã PASS. Mục cuối
  của bàn giao ghi kết quả triển khai thực tế sau khi kích hoạt API.
- Khôi phục/giọng/lipsync trên điện thoại chưa nghiệm thu. Cần dữ liệu có
  quyền dùng, tách người/nguồn để hiệu chỉnh/đánh giá đúng phiên bản mới.

## Bước tiếp theo
1. Hoàn tất parity sau sửa, replay cùng input cố định và kiểm hồi quy.
2. Review, commit mã; cập nhật riêng API snapshot, giữ APK/data/key/profile.
3. Khởi động kiểm chứng server. Không yêu cầu thử lặp lại để tìm ngưỡng đạt.
4. Giữ DraftPR135 và trạng thái doing nếu chưa có nghiệm thu thật.

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
