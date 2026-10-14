// Mọi chữ hiển thị cho người dùng nằm ở đây.
// Khu vực /verify (người dân) KHÔNG được chứa điểm số hay chữ "giả mạo" — có test kiểm.

export const vi = {
  app: {
    name: "VeriClue",
    description: "Hệ thống xác minh danh tính điện tử VeriClue",
  },
  verify: {
    title: "Xác minh danh tính",
    description: "Làm theo hướng dẫn trên màn hình để hoàn tất xác minh.",
  },
  review: {
    title: "Bàn duyệt",
    description: "Danh sách hồ sơ cần nhân viên xem xét.",
  },
  forensic: {
    title: "Giám định",
    description: "Tải lên video hoặc âm thanh cần giám định.",
  },
  // Trang thử nội bộ (CAP-03), không dành cho người dân.
  lab: {
    chromapulse: {
      title: "Thử ChromaPulse (nội bộ)",
      description:
        "Thu số liệu phản chiếu màu trên mặt để nhóm quyết định ở PRES-01. Trang này không dùng cho người dân.",
      privacyTitle: "Dữ liệu được ghi",
      privacy:
        "Trang chỉ ghi số liệu màu và thời gian, không lưu ảnh hay khung hình. Không gửi gì lên máy chủ: kết quả là một file JSON tải về máy của bạn.",
      warningTitle: "Cảnh báo nháy màu",
      warning:
        'Màn hình sẽ đổi màu khoảng 7 giây (dưới 2 lần mỗi giây, màu nhạt). Người nhạy cảm với ánh sáng nhấp nháy không nên thử. Bấm "Dừng" bất cứ lúc nào.',
      accept: "Tôi đã đọc hai mục trên",
      deviceLabel: "Tên máy (ví dụ: Redmi Note 12)",
      scenarioLabel: "Tình huống",
      scenarios: {
        real: "Người thật (mặt tôi trước camera)",
        replay: "Phát lại (camera quay một màn hình khác đang chiếu mặt người)",
        obs: "OBS Virtual Camera (chỉ trên laptop)",
      },
      takeLabel: "Lần thứ",
      noteLabel: "Ghi chú (ánh sáng, khoảng cách...)",
      loadStart: "Bật camera và tải MediaPipe",
      loading: "Đang tải MediaPipe và mở camera...",
      loadError: "Không khởi động được",
      assetsHint:
        "Thiếu file MediaPipe? Chạy: uv run python scripts/fetch_web_assets.py (xem runbook).",
      httpsHint: "Camera trên điện thoại cần HTTPS. Xem hướng dẫn trong runbook.",
      noFrameCallback:
        "Trình duyệt này không hỗ trợ requestVideoFrameCallback: không thu được dữ liệu.",
      faceFound: "Thấy mặt",
      faceNotFound: "Chưa thấy mặt",
      delegate: "Bộ xử lý",
      captureTime: "captureTime",
      captureTimeYes: "có",
      captureTimeNo: "không",
      showRegions: "Hiện khung các vùng đo (để kiểm tra, không lưu)",
      brightnessHint:
        "Tăng độ sáng màn hình tối đa, giữ mặt cách màn hình 25 đến 40 cm, mặt nằm giữa khung hình.",
      start: "Bắt đầu thử",
      countdown: "Giữ yên mặt, bắt đầu sau",
      stop: "Dừng",
      doneTitle: "Xong lần thử",
      framesSummary: "Số khung ghi được",
      faceSummary: "Khung thấy mặt",
      colorsSummary: "Số màu ghi được",
      problemsTitle: "Cần lưu ý",
      noProblems: "Không có vấn đề nào.",
      download: "Tải file JSON",
      again: "Thử lại",
      nextTake: "Lần kế tiếp",
      fileName: "Tên file",
      aborted: "Đã dừng giữa chừng, nên thử lại.",
    },
  },
} as const;

export type ViMessages = typeof vi;
