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
    // Màn đồng ý: chỉ dùng câu chữ và con số có trong tài liệu (proposal, E2-capture). Những mục chưa có
    // trong tài liệu (quyền rút lại hoặc xóa sớm, bên kiểm soát dữ liệu, hạn lưu giọng nói) để trống.
    consent: {
      title: "Đồng ý xử lý dữ liệu",
      sensitive: "Dữ liệu sinh trắc học là dữ liệu nhạy cảm.",
      purposeTitle: "Mục đích",
      purpose:
        "Xác minh danh tính của bạn. Ứng dụng chụp ảnh và quay video ngắn khuôn mặt, đổi màu màn hình trong vài giây để kiểm tra camera, và có thể yêu cầu bạn đọc một câu.",
      retentionTitle: "Thời hạn lưu",
      retention:
        "Ảnh và video tự xóa sau 24 giờ nếu xác minh thành công, hoặc sau 30 ngày nếu hồ sơ cần được xem xét. Dữ liệu chỉ được lưu đúng mục đích và xóa khi hết mục đích.",
      stopAnytime: "Bạn có thể dừng bất cứ lúc nào.",
      checkbox: "Tôi đã đọc và đồng ý cho xử lý dữ liệu sinh trắc học của tôi như trên.",
      continue: "Tiếp tục",
    },
    camera: {
      title: "Cho phép dùng camera",
      description: "Ứng dụng cần camera trước để chụp khuôn mặt của bạn.",
      asking: "Đang mở camera...",
      denied:
        "Bạn chưa cho phép dùng camera. Hãy cho phép trong cài đặt của trình duyệt rồi thử lại.",
      unavailable: "Không mở được camera. Hãy kiểm tra camera rồi thử lại.",
      insecure: "Camera chỉ hoạt động trên kết nối an toàn (HTTPS).",
      retry: "Thử lại",
    },
    framing: {
      title: "Đưa khuôn mặt vào giữa khung hình",
      description: "Giữ điện thoại cách mặt khoảng 25 đến 40 cm, ở nơi đủ sáng.",
      loading: "Đang chuẩn bị camera...",
      allGood: "Tốt, giữ nguyên tư thế",
      ovalLabel: "Khung đặt khuôn mặt",
    },
    // Chỉ dẫn của cổng chất lượng ở web: mỗi lần hiện MỘT câu, CHỈ nói về chất lượng ảnh. "Lại gần hơn" và
    // "Ra chỗ sáng hơn" có trong tài liệu (E2-capture); các câu còn lại do nhóm soạn, đưa vào mô tả PR.
    quality: {
      NO_FACE: "Hãy đưa khuôn mặt vào khung hình",
      MULTIPLE_FACES: "Chỉ để một khuôn mặt trong khung hình",
      FACE_CENTER: "Đưa khuôn mặt vào giữa khung hình",
      MOVE_CLOSER: "Lại gần hơn",
      MOVE_BACK: "Lùi ra xa hơn một chút",
      TURN_STRAIGHT: "Nhìn thẳng vào camera",
      TOO_BRIGHT: "Tránh nắng chiếu thẳng vào mặt",
      LOW_LIGHT: "Ra chỗ sáng hơn",
      HOLD_STILL: "Giữ yên điện thoại và khuôn mặt",
      BLURRY: "Ảnh chưa nét, hãy giữ yên và lau sạch camera",
    },
    // Màn báo riêng khi thiết bị hoặc trình duyệt chưa đáp ứng. Không phải lỗi của người dùng, không gửi gì đi.
    deviceUnsupported: {
      title: "Thiết bị hoặc trình duyệt chưa đáp ứng",
      body: "Hãy thử bằng trình duyệt hoặc thiết bị khác.",
      reasons: {
        low_fps: "Camera hoạt động dưới 15 khung hình mỗi giây.",
        low_resolution: "Camera có độ phân giải thấp hơn 640 x 480.",
        no_frame_callback: "Trình duyệt chưa hỗ trợ đo khung hình của camera.",
      },
      restart: "Thử lại",
    },
    creating: "Đang chuẩn bị phiên...",
    flash: {
      title: "Chuẩn bị đổi màu màn hình",
      warning:
        "Màn hình sẽ đổi màu nhạt trong vài giây. Người nhạy cảm với ánh sáng nhấp nháy không nên tiếp tục. Bạn có thể bấm Dừng bất cứ lúc nào.",
      brightness: "Hãy tăng độ sáng màn hình lên cao và giữ yên khuôn mặt.",
      start: "Bắt đầu",
      stop: "Dừng",
      running: "Giữ yên khuôn mặt...",
      holdTitle: "Giữ yên",
      hold: "Nhìn thẳng vào camera và giữ yên khuôn mặt khoảng 3 giây.",
    },
    uploading: "Đang gửi, vui lòng chờ...",
    result: {
      passTitle: "Xác minh thành công",
      passBody: "Bạn đã hoàn tất xác minh.",
      reviewTitle: "Hồ sơ đang được kiểm tra",
      reviewBody: "Hồ sơ của bạn đang được kiểm tra. Chúng tôi sẽ thông báo khi có kết quả.",
      retryTitle: "Vui lòng thử lại",
      retryAttempts: "Số lần thử còn lại",
      retryButton: "Thử lại",
    },
    // Gợi ý chụp lại: CHỈ nói về chất lượng ảnh. "Ra chỗ sáng hơn" và "Lại gần hơn" có trong tài liệu
    // (E2-capture); 5 câu còn lại do nhóm soạn, đã đưa vào mô tả PR để trưởng nhóm xem.
    retryHints: {
      MORE_LIGHT: "Ra chỗ sáng hơn",
      MOVE_CLOSER: "Lại gần hơn",
      MOVE_BACK: "Lùi ra xa hơn một chút",
      FACE_CENTER: "Đưa khuôn mặt vào giữa khung hình",
      HOLD_STILL: "Giữ yên điện thoại và khuôn mặt",
      QUIET_PLACE: "Chuyển đến nơi yên tĩnh hơn",
      BRIGHTNESS_UP: "Tăng độ sáng màn hình",
    },
    retryHintFallback: "Hãy chụp lại ở nơi đủ sáng và giữ yên khuôn mặt",
    voice: {
      title: "Đọc to câu sau",
      promptLabel: "Câu cần đọc",
      instruction:
        "Bấm “Bắt đầu ghi âm”, đọc to và rõ câu trên, rồi bấm “Dừng và gửi”. Ghi tối đa 8 giây.",
      start: "Bắt đầu ghi âm",
      stop: "Dừng và gửi",
      recording: "Đang ghi âm... hãy đọc câu trên.",
      tooShort: "Đoạn ghi âm quá ngắn. Hãy bấm ghi âm lại và đọc đủ câu.",
      micDenied:
        "Chưa được cấp quyền dùng micro. Hãy cho phép micro trong cài đặt trình duyệt rồi thử lại.",
      micUnavailable: "Không ghi âm được. Hãy kiểm tra micro rồi thử lại.",
      sending: "Đang gửi...",
      attemptsLeft: "Số lần đọc lại còn lại",
    },
    errors: {
      title: "Có sự cố",
      restart: "Bắt đầu lại",
      network: "Không kết nối được. Hãy kiểm tra mạng rồi thử lại.",
      session: "Phiên đã hết hạn hoặc không còn hợp lệ. Hãy bắt đầu lại.",
      conflict: "Không thể tiếp tục phiên này. Hãy bắt đầu lại.",
      tooLarge: "Dữ liệu quá lớn nên chưa gửi được. Hãy bắt đầu lại.",
      invalid: "Dữ liệu gửi đi chưa hợp lệ. Hãy bắt đầu lại.",
      server: "Hệ thống đang bận. Vui lòng thử lại sau ít phút.",
      unexpected: "Có lỗi không mong muốn. Hãy bắt đầu lại.",
      stopped: "Bạn đã dừng. Hãy bắt đầu lại khi sẵn sàng.",
      interrupted: "Phiên bị gián đoạn, ví dụ do chuyển sang ứng dụng khác. Hãy bắt đầu lại.",
    },
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
      previewError: "Lỗi khi nhận diện khuôn mặt",
    },
    // Xem kết quả từng module của một phiên (chỉ khi chạy `npm run dev`).
    session: {
      title: "Kết quả từng module (chỉ để thử)",
      description:
        "Trang nội bộ cho người thử: xem mô hình chấm gì ở một phiên. Chỉ có khi chạy ở chế độ phát triển, người dân không bao giờ thấy trang này.",
      idLabel: "Mã phiên hoặc mã ca",
      load: "Xem",
      loading: "Đang tải...",
      missingId: "Chưa có mã. Mở trang với đường dẫn /lab/session?id=<mã phiên>.",
      notFound:
        "Không có ca duyệt cho mã này. Chỉ phiên có kết quả “review” mới tạo ca; phiên “pass” không có dữ liệu để xem ở đây.",
      needInitial:
        "Bàn duyệt chỉ cho xem ý kiến AI sau khi ghi quyết định ban đầu. Bấm nút dưới để ghi quyết định thử (ghi chú “dev-test”).",
      recordInitial: "Ghi quyết định ban đầu “dev-test”",
      suggestion: "Gợi ý của hệ thống",
      module: "Module",
      status: "Trạng thái",
      gate: "Cổng",
      score: "Điểm thô",
      probAttack: "Xác suất tấn công (đã hiệu chỉnh)",
      version: "Phiên bản mô hình",
      latency: "Thời gian (ms)",
      evidence: "Bằng chứng",
      none: "—",
      error: "Không tải được. Kiểm tra API đang chạy rồi thử lại.",
    },
  },
} as const;

export type ViMessages = typeof vi;
