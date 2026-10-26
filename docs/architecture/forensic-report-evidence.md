# Ảnh và phổ âm báo cáo — FOR-04

HTML ký và gói PDF/JSON ký dùng chung minh họa opt-in. Không đổi UI, detector,
ngưỡng hoặc verdict. Ảnh/phổ thể hiện nội dung vật chứng, không phải heatmap,
lý do AI kết luận, xác suất giọng AI hoặc báo cáo ENFSI đã hiệu chỉnh.

## Bật trên máy demo

```powershell
$env:FORENSIC_REPORT_EVIDENCE='true'
$env:FORENSIC_REPORT_FFMPEG=(Get-Command ffmpeg).Source
```

FFmpeg do người vận hành cài, đường dẫn executable phải tuyệt đối. Không tự tải
theo request, không đóng gói binary trong repo/Docker. Compose chỉ chuyển cấu
hình; container API mặc định chưa có công cụ. CI cài FFmpeg trên runner để test.
Giữ REPORT_SIGNING_KEY_PATH, restart API; PDF vẫn cần Node/Playwright riêng.

Mặc định tắt, không thêm section. Khi bật, chỉ staff xuất được và chỉ done/real
được trích. Thiếu runtime/nguồn, hash sai, decoder lỗi/bận/hết budget: báo cáo
ghi rõ chưa có minh họa, giữ kết quả và chữ ký, không giả ảnh hoặc hạ về MOCK.

## Nguồn và phương pháp

- File thường trong đúng MEDIA_DIR/forensic/job_id, không symlink/junction/path
  do client cung cấp. Copy theo khối vào snapshot tạm riêng, tối đa 64 MiB;
  SHA-256 phải khớp cả job và row trước decode. Chỉ đọc snapshot đã kiểm, không
  ghi đè nguồn. Thay file nguồn sau đó không đổi pixel lần xuất này.
- `report-illustrations-v1` lấy tối đa ba khoảng nghi ngờ đầu tiên, mỗi khoảng
  tối đa ba giây đầu. Ghi rõ các khoảng còn lại không được minh họa.
- Video lấy khung ở giữa cửa sổ, giữ tỷ lệ trong 640×360. Caption ghi **mốc trích
  yêu cầu**, không nhận là PTS decoder chính xác; không dùng ảnh này đo độ trễ.
- Phổ dùng audio mono 16 kHz, `showspectrumpic`, cửa sổ Hann, trục tần số tuyến
  tính, cường độ log. Caption ghi cửa sổ trên timeline vật chứng; trục thời gian
  trong ảnh tính từ đầu đoạn giải mã. Codec/seek có thể làm lệch biên mẫu, đây
  không phải căn thời gian mẫu chính xác hoặc bằng chứng khớp môi. Không giải
  mã được audio thì ghi thiếu phổ, không suy ra im lặng hoặc người thật.
- Ghi version phương pháp/FFmpeg; chỉ nhúng PNG đã kiểm giới hạn, CRC, IDAT/IEND
  dưới dạng data URL, mọi text escape HTML. Không nhận SVG/URL/filter từ client.

Ảnh được đưa vào trước ký HTML hoặc tính hash PDF. Chữ ký bảo vệ đúng byte
HTML/PDF chứa ảnh và chú thích; không thêm member ZIP hoặc đổi protocol/schema.
Snapshot/PNG không persist riêng, thư mục tạm dọn khi xong; không tuyên bố secure
erase, TEE hoặc zero retention. HTML đã lưu và PDF người dùng tải chứa dữ liệu
vật chứng, áp dụng chính sách lưu hiện hành.

## Giới hạn thực thi

Một lượt trích/process API, bận thì ghi thiếu minh họa. Budget tổng 20 giây,
từng FFmpeg tối đa bốn giây; decoder/filter/encoder một thread. Chỉ protocol
file/pipe, demuxer mov, matroska/webm, wav, mp3, ogg, flac, aac; không HLS/DASH/
concat/image2. Không shell; env không có API secrets, proxy, FFREPORT/NODE_OPTIONS.
Stderr native bỏ, lỗi không lộ path hoặc nội dung. Timeout subprocess kết thúc
process FFmpeg của lượt đó.

Mỗi allocation FFmpeg tối đa 16 MiB, không phải giới hạn RAM tổng hay sandbox.
Mỗi lệnh một PNG, tối đa 384 KiB/1200×720; ảnh quá lớn/hỏng bị bỏ kèm ghi chú.
HTML/PDF vẫn có giới hạn tổng của PR85. Deadline có kiểm copy/hash nhưng disk
I/O, spawn và cleanup không phải SLA cứng. Binary phải đáng tin, filesystem cần
quyền phù hợp; whitelist không thay thế cô lập máy xử lý.

## Kiểm chứng

Test dùng nguồn/PNG tổng hợp, không phải số liệu mô hình. Test native tạo video
test-pattern/sóng sin, kiểm frame/phổ giải mã được, nguồn không đổi. Playlist URL
HTTP loopback của chính test bị từ chối, server không nhận request. Biến
TEST_FFMPEG_BINARY bật test này; CI Python đã cấu hình FFmpeg thật.
PDF QA render bằng Chromium/Poppler và xem đủ trang, xác minh gói có chữ ký.

Tham chiếu: [showspectrumpic](https://ffmpeg.org/ffmpeg-filters.html#showspectrumpic),
[protocol whitelist](https://ffmpeg.org/ffmpeg-protocols.html#Protocol-Options).
FOR-04 còn liên kết/neo audit, LR/calibration/thang lời ENFSI và UI nghiệm thu.
