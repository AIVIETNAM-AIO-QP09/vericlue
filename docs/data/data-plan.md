# Kế hoạch dữ liệu cho bản demo VeriClue (BTL86-16)

> Kiểm tra ngày 14/10/2026. Nguyên tắc: **chỉ dùng dữ liệu và mô hình có sẵn, không tổ chức thu dữ liệu.**
>
> - **Có** — đã mở trang hoặc API, xác nhận còn tải được.
> - **Một phần** — có tồn tại, nhưng chưa xác nhận hết chi tiết.
> - Gần như mọi bộ dữ liệu đều **chỉ dùng cho nghiên cứu, phi thương mại**. Demo cuộc thi thì không sao, nhưng phải trích dẫn nguồn gốc (không trích bản mirror).

---

## 1. Tóm tắt: thành phần nào dùng dữ liệu gì

| Thành phần | Mô hình có sẵn (không cần train) | Dữ liệu người Việt / bối cảnh Việt | Dữ liệu bổ trợ |
|---|---|---|---|
| **Chống giả mạo khuôn mặt (PAD)** | face-antispoof-onnx (Apache-2.0, 600 KB); Silent-Face MiniFASNet (Apache-2.0) | **Zalo AI 2022 Liveness**; **Face_anti_spoofing (người Việt)** | CelebA-Spoof; LCC-FASD |
| **Deepfake khuôn mặt** | Effort (CC BY-NC); DeepfakeBench Xception (CC BY-NC) | *Không có bộ công khai* → tự tạo từ ảnh người nổi tiếng Việt (mục 3) | **RTFS-10k** (face-swap kiểu Deep-Live-Cam); **WildDeepfake** (đã nén, ngoài đời) |
| **Giọng giả tiếng Việt** | Gustking XLS-R (Apache-2.0); AASIST (MIT); PhoWhisper (BSD-3) | **MLAAD `fake/vi`**; **ViSpoofDB**; **VSASV**; **ViMD** (giọng thật 63 tỉnh) | ASVspoof 5; CodecFake+ |
| **Khớp môi–âm** | SyncNet (MIT); LipFD (đã có checkpoint) | **ViCocktail** (video người Việt nói, 271 giờ) | LAV-DF; PolyGlotFake |
| **Chế độ giám định (video nén)** | Dùng lại các mô hình trên | Nén lại bằng ffmpeg từ dữ liệu ở trên | WildDeepfake; Deepfake-Eval-2024 (chỉ dùng để đánh giá) |
| **ChromaPulse, CamProbe** | Không cần mô hình học máy | *Bản chất không thể có dữ liệu sẵn* (mục 4) | — |

---

## 2. Chi tiết từng bộ dữ liệu

### 2.1 Khuôn mặt — chống giả mạo

| Bộ dữ liệu | Nội dung | Người Việt? | Cách lấy | Giấy phép | Đường dẫn | Kiểm tra |
|---|---|---|---|---|---|---|
| **Zalo AI 2022 Liveness** (bản mirror đầy đủ) | 2,81 GB. Tập train: 1.168 video selfie 1–5 giây, có nhãn. Các tập test **không có nhãn**. Tấn công: phát lại, ảnh in | **Có** | Kaggle, tải ngay | Người đăng ghi MIT; điều khoản gốc của Zalo chưa rõ | kaggle.com/datasets/hlly34/liveness-detection-zalo-2022 | Có |
| **Face_anti_spoofing** (Mai Hoàng Tùng) | 8,90 GB theo API Kaggle, 11.376 ảnh: thật / chụp lại màn hình. Đã chia sẵn train và test | **Có** | Kaggle, tải ngay | CC BY 4.0 | kaggle.com/datasets/maihongtng/face-anti-spoofing | Có |
| CelebA-Spoof | 625.537 ảnh, 10.177 người | Không | Google Drive, tải ngay | Phi thương mại | github.com/ZhangYuanhan-AI/CelebA-Spoof | Có |
| LCC-FASD | 5,2 GB | Không | Kaggle, tải ngay | Không rõ | kaggle.com/datasets/faber24/lcc-fasd | Có |

**Cách dùng:** chia tập train Zalo (đã có nhãn) theo người thành phần hiệu chỉnh và phần kiểm tra. Tập Face_anti_spoofing dùng làm bộ kiểm tra thứ hai trên người Việt.

### 2.2 Khuôn mặt — deepfake

| Bộ dữ liệu | Nội dung | Cách lấy | Giấy phép | Đường dẫn | Kiểm tra |
|---|---|---|---|---|---|
| **RTFS-10k** | 9.772 video face-swap: 4.875 inswapper + 4.897 uniface; 1.636 video gốc, có CSV truy vết nguồn/donor. 17,66 GB | Kaggle, tải ngay | CC BY-SA 4.0 | kaggle.com/datasets/stplusplus/rtfs-10k | Có |
| **WildDeepfake** | Khoảng 1,16 triệu khung hình deepfake lấy từ Internet, đã bị nén. 72,8 GB (có thể tải một phần) | HF, tải ngay | Apache-2.0 (theo trang) | huggingface.co/datasets/xingjunm/WildDeepfake | Có |
| FaceForensics++ | Bộ chuẩn, có mức nén c23 và c40 | Điền form, chờ khoảng 1 tuần | Điều khoản riêng | github.com/ondyari/FaceForensics | Có |
| DeepSpeak v1 | Video webcam, có **FaceFusion Live** (face-swap thời gian thực) và lip-sync | HF, điền form | Riêng | huggingface.co/datasets/faridlab/deepspeak_v1 | Có |
| Deepfake-Eval-2024 | Deepfake thật lấy từ mạng xã hội, 52 ngôn ngữ. **Chỉ được dùng để đánh giá, cấm dùng để huấn luyện** | HF, duyệt thủ công | CC BY-SA 4.0 | huggingface.co/datasets/nuriachandra/Deepfake-Eval-2024 | Có |

### 2.3 Ảnh khuôn mặt người Việt (nguồn để tự tạo deepfake)

| Bộ dữ liệu | Nội dung | Cách lấy | Giấy phép | Đường dẫn | Kiểm tra |
|---|---|---|---|---|---|
| **Vietnamese Celebrity Faces** | 8.557 ảnh, khoảng 224 người nổi tiếng | Kaggle / HF, tải ngay | HF ghi Apache-2.0 | kaggle.com/datasets/duongtran1909/vietnamese-celebrity-faces | Có |
| VN-Celeb | Khoảng 23 nghìn ảnh, khoảng 1.020 người | Kaggle, tải ngay | Người đăng ghi MIT | kaggle.com/datasets/duypok/vn-celeb | Một phần |
| **ViCocktail** | 271 giờ **video người Việt đang nói** (114 GB, có thể tải một phần) | HF, tải ngay | Không ghi | huggingface.co/datasets/nguyenvulebinh/ViCocktail | Có |

### 2.4 Giọng nói tiếng Việt — giả và thật

| Bộ dữ liệu | Nội dung | Cách lấy | Giấy phép | Đường dẫn | Kiểm tra |
|---|---|---|---|---|---|
| **MLAAD — thư mục `fake/vi`** | Giọng giả tiếng Việt từ 5 hệ TTS (gồm viXTTS, VieNeu-TTS), mỗi hệ ≥ 1.000 clip. Chỉ có giọng giả | HF, đồng ý điều khoản là tải ngay; chỉ cần tải thư mục `vi` | CC BY-NC 4.0 | huggingface.co/datasets/mueller91/MLAAD | Có |
| **ViSpoofDB** | 14.195 clip. Giọng thật từ VIVOS/VLSP; giọng giả từ **FPT.AI, Viettel, ElevenLabs**, Coqui; có thêm tập gTTS chưa từng thấy. Khoảng 2,4 GB | Google Drive công khai | Không ghi | github.com/studie-e/Vietnamese-Audio-Deepfake-Detection | Có |
| **VSASV** | Bộ chống giả giọng tiếng Việt lớn nhất (69 GB). Chủ yếu là tấn công phát lại; tác giả ghi bản phát hành **chưa đầy đủ** | HF, đồng ý điều khoản là tải ngay | CC BY-NC 4.0 | huggingface.co/datasets/hustep-lab/VSASV-Dataset | Có |
| SEA-Spoof (phần tiếng Việt) | 81.020 câu tiếng Việt, nhiều hệ TTS/VC | Gửi email xin tác giả, chờ vài ngày | Phi thương mại | huggingface.co/datasets/Jack-ppkdczgx/SEA-Spoof | Có |
| **ViMD** | **Giọng thật 63 tỉnh thành**, 102,6 giờ, có nhãn tỉnh, vùng miền và giới tính. 59,8 GB | HF, **không cần đăng ký** | CC BY-NC-ND 4.0 | huggingface.co/datasets/nguyendv02/ViMD_Dataset | Có |
| VIVOS, FOSD | Giọng đọc thật, 15 giờ và 100 giờ | HF, tải ngay | CC BY-NC-SA / CC BY | HF | Có |
| ~~VietPrism~~ | Có trên paper nhưng **chưa phát hành dữ liệu** | — | — | arXiv 2609.30005 | — |

**Cách ghép dữ liệu:**
- Huấn luyện / hiệu chỉnh: giọng thật **ViMD** (lấy đều ba miền) + giọng giả **MLAAD `fake/vi`**.
- Kiểm tra trên công cụ chưa từng thấy: **ViSpoofDB**, vì giọng FPT.AI, Viettel, ElevenLabs không có trong MLAAD.

Cách này cho phép **báo cáo kết quả theo miền Bắc / Trung / Nam**, đúng yêu cầu "giọng nói các vùng miền" của đề.

### 2.5 Nghe–nhìn (khớp môi–âm)

| Bộ dữ liệu | Nội dung | Cách lấy | Giấy phép | Kiểm tra |
|---|---|---|---|---|
| LAV-DF | Video bị sửa cục bộ cả hình lẫn tiếng (tiếng Anh). 25,6 GB | HF, tải ngay sau khi đồng ý | CC BY-NC 4.0 | Có |
| PolyGlotFake | 15 nghìn video nhiều ngôn ngữ, có tiếng Trung và tiếng Nhật | Google Drive, tải ngay | Chỉ dùng nghiên cứu | Có |
| FakeAVCeleb | 20 nghìn video, đa sắc tộc | Điền form | Điều khoản riêng | Có |

---

## 3. Khoảng trống: tự **tạo** từ dữ liệu có sẵn, không phải tự **thu**

Không có bộ dữ liệu công khai nào chứa **deepfake khuôn mặt hay nghe–nhìn của người Việt**, cũng như video **đã nén qua Zalo / Facebook / TikTok**. Cách xử lý dưới đây chỉ dùng dữ liệu công khai:

| Thiếu | Cách tạo | Công cụ |
|---|---|---|
| Deepfake khuôn mặt người Việt | Ghép mặt từ *Vietnamese Celebrity Faces* vào video *ViCocktail* | FaceFusion / inswapper |
| Deepfake nghe–nhìn tiếng Việt | Lấy giọng giả MLAAD-vi rồi lip-sync lên video ViCocktail | Wav2Lip / LatentSync |
| Video nén mạng xã hội | Nén lại các video trên: H.264 CRF 28–40, giảm xuống 480p; âm thanh Opus/AMR 8 kHz | ffmpeg |

Toàn bộ dữ liệu tự tạo **chỉ dùng nội bộ để kiểm thử, không phát tán**. Nên ưu tiên ảnh của người có tiếng đã công khai, tránh làm deepfake người thường. Ghi rõ trong báo cáo đây là dữ liệu tổng hợp phục vụ nghiên cứu.

---

## 4. ChromaPulse và CamProbe: vì sao không có dữ liệu sẵn và làm thế nào

- Hai thành phần này đo **phản ứng của khuôn mặt với chuỗi màu do chính hệ thống phát ra lúc đang chạy**, và **hành vi của camera trên trình duyệt**. Vì vậy không thể có bộ dữ liệu quay sẵn — video quay sẵn không "biết" chuỗi màu của phiên mới.
- **Với mục tiêu demo:** 5 thành viên tự chạy thử trên 2–3 điện thoại và laptop của mình, khoảng 10–15 phút. Thử ở vài mức ánh sáng; cho chạy qua OBS Virtual Camera và Deep-Live-Cam để xem hệ thống phản ứng thế nào, rồi chỉnh ngưỡng.
- Đây là **kiểm thử phần mềm**, không phải thu dữ liệu: không tuyển tình nguyện viên, không dùng để huấn luyện, xóa sau demo.

---

## 5. Danh sách tải

**Tải ngay hôm nay (không cần chờ duyệt):**
- Zalo AI 2022 (2,8 GB)
- Face_anti_spoofing (8,90 GB theo API Kaggle)
- RTFS-10k (17,7 GB)
- Vietnamese Celebrity Faces
- ViSpoofDB (2,4 GB)
- ViMD (tải một phần theo vùng)
- VIVOS
- MLAAD `fake/vi` (đồng ý điều khoản là tải ngay)
- VSASV (đồng ý điều khoản là tải ngay)
- LAV-DF
- ViCocktail (tải một phần)
- WildDeepfake (tải một phần)
- Toàn bộ mô hình ở mục 1

**Gửi yêu cầu ngay (không bắt buộc cho demo, có thì tốt hơn):**
- SEA-Spoof: gửi email cho tác giả
- FaceForensics++
- DeepSpeak v1
- Deepfake-Eval-2024

**Dung lượng:** khoảng 100–150 GB nếu chỉ tải phần cần thiết. DATA-01 mặc định `--subset small` có ngân sách 28,4 GB gồm cache/giải nén; đây là giới hạn thiết kế, phải chạy đủ danh mục mới nghiệm thu dung lượng và thời gian. Số byte nguồn FAS-VN/RTFS ở trên được đối chiếu API Kaggle khi làm DATA-01 ngày 15/10/2026.

---

## 6. Lưu ý

- **Nhãn:** các tập test của Zalo không có nhãn. Chỉ tập train (1.168 video) có nhãn, nên phải tự chia tập này.
- **Không phải dữ liệu eKYC thật:** MLAAD-vi chỉ có giọng giả; RTFS-10k là video YouTube. Kết quả demo vì vậy **không đại diện cho môi trường eKYC thật**, cần ghi rõ trong báo cáo.
- **Độ chính xác trên model card:** các con số trên trang mô hình Hugging Face thường đo trên chính dữ liệu huấn luyện, nên sẽ giảm khi gặp dữ liệu thật. Luôn kiểm tra lại trên Zalo, ViSpoofDB và RTFS-10k.
