# Chuẩn bị dữ liệu giọng NES2Net trên Colab

Notebook sinh từ source đã test, không sửa tay file ipynb:

```powershell
uv run python scripts/build_voice_data_notebook.py
uv run python scripts/build_voice_data_notebook.py --check
```

Mở `prepare_nes2net_data.ipynb` trên Colab bằng tài khoản hiện có, giữ private và
dùng CPU mặc định. Không mount Drive, không token, không GPU hoặc tạo clone.
Nếu dịch vụ yêu cầu chấp thuận điều khoản mới, chủ tài khoản cần chấp thuận hoặc
ủy quyền đúng bước đó; không tự bỏ qua hộp điều khoản. Job chưa chạy khi bị chặn.
Cell đầu nhúng script/commit/SHA, từ chối source chưa commit; tải DNU publisher
revision cố định, kiểm file/SHA/PCM và xuất gói. Cell cuối tải bundle đã kiểm.

`scripts/prepare_nes2net_data.py` cũng chạy trực tiếp trên Kaggle/Colab:

```bash
python prepare_nes2net_data.py --output-root /content/vericlue-dnu-bonafide --source-commit <commit-da-kiem> --per-speaker 20 --seed 42 --archive /content/vericlue-dnu-bonafide.zip
```

Chọn theo hash ID trước inference, giữ người train→calib_fit,
validation→calib_ltt, test→test_only. Không cắt/normalize/resample âm thanh để
khớp model; chỉ nhận WAV gốc mono16k/PCM16/1–30giây. File lỗi hoặc đổi hash giữ
lại và ghi incomplete; chạy lại dùng file đã kiểm, không ghi đè audio.

Gói chỉ gồm manifest, source/license/metadata publisher, audio đã khai và report
kiểm tra. Không quét/gói file ngoài danh sách; kiểm lại hash trước khi archive.
Nhận bundle về laptop theo quy trình ADR0015 rồi chạy
`eval.nes2net_utterance prepare` để kiểm lại độc lập.

**Đây chỉ là lớp thật, calibration_ready luôn false.** Vẫn cần lớp tấn công có
quyền dùng, mã người/reference/nguồn, chia nhóm và giữ test trước khi collect/fit.
Không tạo calibrator hoặc mở chốt từ bundle này. Không dùng VIVOS parity.
