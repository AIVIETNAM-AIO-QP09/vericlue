# Real AI phone demo — Implementation Plan

> For agentic workers: subagent-driven-development, TDD và review độc lập. Các phần Android và ML/API có ownership riêng, chạy song song theo yêu cầu tăng tốc của người dùng; chỉ root commit/tích hợp/build. Không xóa worktree hoặc dữ liệu cũ.

**Goal:** chuẩn bị server + APK để sáng 02/11 người dùng thử Android thật: model thực suy luận, ngưỡng thủ công có nhãn, OTP mô phỏng, ba luồng tài khoản demo.

**Architecture:** hoàn thiện MANUAL_FULL_DEMO hiện có, chỉ synthetic+mvp, mode/policy gắn phiên và tài khoản. Worker manual riêng dùng raw AntiDeepfake và SyncNet thành công thật; không đổi diagnostic NES2Net, không fake calibrator. Android mở API thật mặc định trong APK giao, giữ mode/policy qua lưu/khôi phục và giữ nhãn ở mọi màn hoàn tất.

**Tech Stack:** FastAPI/Pydantic/PyTorch workers, Kotlin/Compose/DataStore, Gradle/JDK17, SQLite migrations0011, private local launcher.

**Spec:** yêu cầu người dùng AI chạy thật + ngưỡng tạm; APP-01/FLOW-04/SEC-09; existing manual-face-demo.md và mobile-privacy-integration.md. Các contract hiện có đã truyền manual_full_demo/mode/hash; không mở rộng HTTP schema trong task này.

## Global Constraints

- Không đổi contracts/thresholds.yaml/ADR/proposal/STATUS. Không merge main. Không reset/xóa WIP/account/model/media, không khởi động cleanup trên DB/media gốc.
- Giữ status error/degraded/not_applicable; không đổi kết quả NES2Net diagnostic thành ok/pass. Không fake probability/artifact hoặc kết quả thành công.
- Mọi ngưỡng mới chỉ policy demo, configurable/internal, hash/version và calibrated=false; mặc định tắt ngoài manual_full_demo. Không chọn từ VIVOS32 hoặc test/điểm DNU; không tuyên bố accuracy.
- Model/metadata sai phiên bản, thiếu score/evidence hoặc policy không khớp đều fail closed. Standard/mixed/protected giữ guard cũ.
- Không lộ điểm cho người dân; demo hiển thị nhãn chưa hiệu chỉnh. Giữ OTP mô phỏng, consent và ký media/P-256 thật, không phát credential/ký kết quả sản phẩm.
- DataStore bổ sung metadata cục bộ, không đổi AccountReceipt API. Giữ receipt/khóa cũ khi thao tác lỗi, không auto-delete legacy account.
- Native smoke và launcher mới dùng DB/media demo tách biệt, model đọc từ cache có sẵn; khóa/HMAC demo ổn định riêng. Không dùng profile/cơ sở dữ liệu cũ cho lifespan cleanup.

## Review Focus

Handshake/worker mode và policy binding; không có đường promote degraded; nguyên vẹn backend version; inference lỗi không pass; chống replay/crossmode; đăng nhập/khôi phục sau restart; debug coldstart không scripted success; nhãn demo qua mọi route; bản ký APK giữ cùng chứng chỉ; không gọi test giả là nghiệm thu máy thật.

## Task 1: Complete manual voice and continuity (ML/API ownership)

Read common/manual_demo.py, runtime/voice_{wire,worker,client}.py, SessionVoiceDetector, API orchestrator/config/session_flow/accounts and tests.

- Manual voice backend **AntiDeepfake** hiện có trả raw score [0,1], status ok khi suy luận thành công. Manual lipsync dùng raw **SyncNet** hiện có. NES2Net và worker diagnostic tiêu chuẩn giữ nguyên.
- Thêm spoof_max và lipsync_max vào ManualDemoThresholds + settings, defaults **0.50** mỗi cái, gt0/lt1/finite; ghi rõ ngưỡng minh họa demo, không fit. Tất cả tham số nằm trong policy hash có version mới. Backend version/result có suffix manual và marker/hash, calibrated=false/prob_attack=None.
- Adapter/evaluator manual chỉ gate raw status ok, finite score đúng module/version và evidence hợp lệ. SyncNet cần splice_flags=0 đúng kiểu/finite và offset/confidence hợp lệ; giữ evidence nguồn, hardware_clock_verified=false. Không nhận mock/diagnostic-only/error/degraded.
- Tách worker kinds/mode handshake rõ; policy client+worker đóng băng lúc tạo. Orchestrator chỉ chọn raw manual path khi manual_full_demo true. Không cho metadata do citizen tự đưa chọn mode/threshold.
- Worker preload ở đường manual phải thực sự nạp model cần thiết trước khi được đánh dấu ready (tránh healthz chỉ kiểm python file). Giữ thời gian startup tách hợp lý khỏi inference; không kéo model/mạng khi chạy.
- SessionFlow + AccountStore kiểm exact manual voice/lipsync policy/hash/version trước pass/receipt; không còn fallback generic probability làm bằng chứng manual. Policy đổi giữa phiên/tài khoản => từ chối, không chuyển mode ngầm.
- Khi manual policy hiện diện, FaceContinuityDetector/factory không lấy artifact calibration cấu hình cũ ghi đè policy; test cả stale/valid path và standard giữ yêu cầu calibrator.
- TDD cho raw success/manual threshold boundaries, failures/missing evidence/nonfinite/splice/version/policy mismatches, worker scope/handshake, required lipsync khi voiced enrollment/recovery, standard diagnostic không đổi; preload thật với fake lightweight backends trong unit. Không full suite/model execution từ worker.
- Không sửa Android, docs, migrations hay repo scripts. Báo interfaces/config/build constants cho root.

## Task 2: Android API-default and durable demo labels (Android ownership)

- Thêm Gradle option **vericlue.liveByDefault**, debug mặc định false để giữ gallery workflow, release luôn true. BuildConfig **LIVE_API_DEFAULT**; FlowState.live lấy flag, APK giao build true. Không fallback sang scripted outcomes khi API lỗi.
- StoredAccount thêm evaluationMode/demoPolicyId lấy từ LiveFlow đã xác nhận; serialize/restore tương thích dữ liệu cũ nhưng unknown không được giả là standard hoặc manual. Không đổi AccountReceipt contract.
- Đối chiếu metadata đã lưu với session mới khi reauth/recovery; giữ receipt/key cũ nếu lỗi/mismatch, không xóa account/alias tự động. Nếu legacy metadata chưa biết, yêu cầu flow xác nhận thích hợp thay vì đoán mode.
- Nhãn “Demo · Ngưỡng chưa hiệu chỉnh” vẫn có ở Success, BankOpened và entry account demo được khôi phục. Offline gallery rõ là preview, không bị trình bày như kết quả model thật.
- Test onboarding/reauth/recovery mode/hash + voice mismatch, restore/legacy và policy change, fresh FlowState API-default và lỗi server không success. Giữ behavior chuẩn/giảm chuyển động/privacy.
- Ownership apps/android code/tests/build config; không API/contracts/README/doc edits. Không Gradle/build/ADB từ worker; root chạy một lượt sau tích hợp, tránh lock.

## Task 3: Isolated runtime, native verification and package (root)

- Kiểm model files/runtime compatibility và cài phần phụ thuộc thực sự thiếu vào runtime riêng nếu cần; không đổi weights hoặc benchmark-test set, không download/login/terms ngoài phạm vi đã được phép.
- Profile server mới tại thư mục private riêng cho 02/11: models paths có sẵn, simulated OTP, encryption/HMAC/sign media hợp lệ, fresh migrated DB/media, calibrated identity artifact fields không cần trong manual được bỏ trống. Không dùng DB/media gốc; không in .env/keys.
- Native warmup chứng minh từng backend/model version thực đã nạp; real audio inference smoke chọn cố định calib_fit đã cho phép, không fit/chọn threshold. Không làm dữ liệu mặt giả thành success; toàn luồng thật vẫn chờ người dùng quay trực tiếp.
- Synthetic integration tests phải đi qua three-flow orchestration/receipt/L0/recovery với guard thật, model fixtures có nhãn chỉ chứng minh logic. Rerun model failures/policy changes/signing/consent/account rollback tests.
- Build Android test/lint/APK với localhost8421,signedMedia=true,presenceTrace=false,liveByDefault=true. Dùng debug signer laptop hiện có, chứng chỉ so với APK đã chuẩn bị, không tạo key mới hoặc dùng distribution signer khác.
- Tạo bundle mới: APK + SHA/build-info commit/options/signer, launcher start/status/stop đúng instance/runtime, ADB install-r/reverse hướng dẫn giữ dữ liệu, checklist ba luồng và danh sách chưa hoàn thiện. Source/worktree/model refs rõ, không nhét data/model/secrets vào Git.
- Review độc lập từng phần và toàn branch, lint/test/plan_check; cập nhật APP/FLOW taskcard/backlog và handoff. Draft PR khi phù hợp, không merge.

## Completion and limitations

“Sẵn sàng thử điện thoại” chỉ khi model warmup/inference checks, API integration và APK checks được ghi bằng chứng. Mọi bước CCCD/mặt/giọng/thiết bị chưa làm ghi **not_run**, không gọi đã nghiệm thu ba luồng. Cuối phiên ghi rõ phần còn thiếu, cách chạy ngày02/11, và lỗi cần người dùng báo lại.

## Rulings / progress

- Ruling: thực hiện trong thiết kế manual_full_demo đã có và được người dùng chấp thuận; không xin lại lựa chọn hướng. Hoàn thiện đường model raw có version riêng, không nới chốt standard hoặc promote kết quả diagnostic.
- Ruling: defaults0.50 là mốc demo công khai, không suy từ dữ liệu; model thật có thể từ chối lượt thử. Không hứa mọi lượt sẽ pass.
- Ruling: một profile/DB/media mới tránh cleanup và đụng tài khoản/khóa gốc. Gói mới không thay file cũ; cài đè chỉ khi điện thoại có mặt.
- Task1/2: pending implementers. Task3: root active inventory/profile; chưa start model/server nào.
