# third_party — Ghi nhận mã nguồn dùng lại

Mọi đoạn code **chép** từ dự án khác phải được ghi vào bảng dưới đây, và file chép phải giữ nguyên dòng giấy phép ở đầu. Đây là điều kiện bắt buộc của giấy phép Apache-2.0 và MIT.

| Nguồn | Giấy phép | Chép vào đâu | Đã sửa gì | Task |
|---|---|---|---|---|
| aws-amplify/amplify-ui `packages/react-liveness` | Apache-2.0 | `apps/web/src/lib/capture/vendor/amplify/` | (điền khi chép) | CAP-04 |
| abrahamjuliot/creepjs `src/lies` | MIT | `apps/web/src/lib/capture/vendor/creepjs/` | (điền khi chép) | CAP-05 |

Văn bản giấy phép gốc lưu trong `third_party/licenses/<tên-dự-án>.txt`.

## Thư viện và mô hình dùng nguyên bản (không chép mã)

Không chép vào `src/`, nhưng vẫn ghi nhận để giữ đúng giấy phép. File tải bằng script, **không commit** (`apps/web/public/mediapipe/` nằm trong `.gitignore`).

| Nguồn | Giấy phép | Dùng ở đâu | Cách lấy | Task |
|---|---|---|---|---|
| `@mediapipe/tasks-vision` 1.1.0 (google-ai-edge/mediapipe) | Apache-2.0 (theo gói npm) | `apps/web/src/lib/capture/chromapulse/landmarker.ts`; wasm chép vào `apps/web/public/mediapipe/wasm/` | `npm ci`, rồi `uv run python scripts/fetch_web_assets.py` | CAP-03 |
| `face_landmarker.task` (float16, v1) | Apache-2.0 theo công bố của Google — **cần kiểm lại** model card và điều khoản dữ liệu huấn luyện | `apps/web/public/mediapipe/face_landmarker.task` | `scripts/fetch_web_assets.py` tải từ `https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task`, kiểm SHA-256 `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff` (3.758.596 byte) | CAP-03 |

Giữ nguyên thông báo Apache-2.0 khi phân phối. Sau này gộp mô hình vào `models/manifest.yaml` (DATA-02).

## Giấy phép KHÔNG được chép vào sản phẩm

GPL, AGPL, LGPL (ví dụ Deep-Live-Cam, DeepFaceLive, pyVHR, heartbeat-js, Sherloq), và **repo không có giấy phép** (mặc định giữ mọi quyền). Những repo này chỉ được dùng để tham khảo ý tưởng hoặc làm công cụ thử tấn công.

## VOICE-04

Không chép mã nguồn thư viện vào repo:

| Thành phần | Giấy phép | Cách dùng |
|---|---|---|
| [webrtcvad-wheels](https://github.com/daanzu/py-webrtcvad-wheels/blob/release/LICENSE) | MIT wrapper; BSD-3-Clause WebRTC | Dependency optional voice; VAD CPU, không checkpoint |
| [Transformers](https://github.com/huggingface/transformers/blob/v4.57.1/LICENSE) | Apache-2.0 | Đọc PhoWhisper local, không remote code |
| [PhoWhisper](https://huggingface.co/vinai/PhoWhisper-small/blob/a86b604c346caf7148c37512eafe783a16420adb/README.md) | BSD-3-Clause | Weights ngoài repo, theo manifest DATA-02 |
| [eSpeak NG 1.52.0](https://github.com/espeak-ng/espeak-ng/blob/1.52.0/COPYING) | GPL-3.0-or-later | **Công cụ thử nghiệm độc lập**, chỉ tạo TTS nội bộ trong DATA_DIR; không chép/link/import vào sản phẩm và không phân phối binary/audio |

eSpeak GPL §2 cho phép chạy công cụ; không suy ra output có giấy phép CC/public
domain. Script chuẩn bị ghi phiên bản, SHA-256 và nguồn ở SOURCE.md cạnh fixture.

TTS thử nghiệm còn dùng [facebook/mms-tts-vie](https://huggingface.co/facebook/mms-tts-vie/blob/b58928d033932a49aa8e3d6cf11625b25fe928d2/README.md), weights **CC BY-NC 4.0**, chỉ nghiên cứu phi thương mại. Model ngoài repo trong MODELS_DIR; không chép code, không gọi ở inference sản phẩm. Script chuẩn bị ghim revision/SHA, không gán giấy phép Transformers cho weights.
