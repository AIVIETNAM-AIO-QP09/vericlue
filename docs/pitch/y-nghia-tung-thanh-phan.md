# Ý nghĩa của từng bước, từng thành phần trong VeriClue

> Mỗi mục trả lời ba câu: **Nếu thiếu thì chuyện gì xảy ra?** → **VeriClue làm gì?** → **Được gì?**
> Dùng cho phần hỏi đáp với mentor, báo cáo, và khi giải thích cho thành viên mới. Ngày 22/10/2026.
> Đây là phần lập luận, không phải số liệu. Mọi con số cụ thể vẫn phải có nguồn.

---

## 0. Trước khi người dùng làm gì

### 0.1 Ngân hàng mở phiên từ máy chủ của họ
- **Vấn đề:** nếu ai cũng tự mở được một phiên xác minh, kẻ gian có thể thử đi thử lại vô hạn để dò điểm yếu, hoặc lấy một kết quả "đạt" của phiên này đem dùng cho giao dịch khác.
- **Làm gì:** chỉ máy chủ ngân hàng được mở phiên, kèm một mã ngẫu nhiên của ngân hàng. Phiên chỉ sống khoảng năm phút.
- **Giá trị:** mỗi kết quả gắn chặt với đúng một yêu cầu của đúng một ngân hàng. Kết quả không thể "tái sử dụng" ở nơi khác hay lúc khác.

---

## Giai đoạn A · Bạn là ai

### A1. Đồng ý tách ba mục
- **Vấn đề:** dữ liệu khuôn mặt và giọng nói là dữ liệu nhạy cảm nhất của một người. Một nút "Đồng ý tất cả" khiến người dân không biết mình đang cho phép điều gì; sau này họ mất niềm tin, còn bên vận hành gặp rủi ro pháp lý.
- **Làm gì:** tách riêng ba việc (xử lý khuôn mặt và giọng nói · lưu mẫu khuôn mặt · lưu thông tin CCCD), nói rõ dữ liệu không dùng để huấn luyện AI.
- **Giá trị:** người dân hiểu và chủ động quyết định; hệ thống có bằng chứng đồng ý rõ ràng cho từng mục đích.

### A2. Số điện thoại và mã OTP
- **Vấn đề:** nếu bỏ qua bước này, kẻ gian có thể mở hàng loạt hồ sơ mà không cần nắm bất kỳ thứ gì thuộc về người thật. Ngân hàng cũng không có kênh để liên lạc hay báo kết quả xét duyệt.
- **Làm gì:** xác nhận người dùng đang giữ số điện thoại đó, có giới hạn số lần nhập sai.
- **Giá trị:** thêm một lớp "bạn đang giữ thứ gì" trước lớp "bạn là ai". Đây là bước rẻ nhất, nên chặn sớm những kẻ gian không đầu tư, trước khi đụng tới dữ liệu sinh trắc. Đồng thời ngân hàng có kênh báo kết quả.

### A3. Chụp hai mặt căn cước
- **Vấn đề:** không có giấy tờ thì không có "mốc" để biết khuôn mặt trước camera phải giống ai. Nếu cho người dùng tự gõ thông tin, kẻ gian khai gì cũng được.
- **Làm gì:**
  - chụp bằng **camera sau**;
  - đọc thông tin từ mã QR trên thẻ;
  - **cắt ảnh chân dung** trên thẻ làm mốc so mặt;
  - kiểm tra thẻ này đã được dùng để đăng ký chưa.
- **Giá trị:** thông tin danh tính lấy từ thẻ, không do người dùng gõ; có ảnh mốc cho bước so mặt; một căn cước không mở được nhiều hồ sơ, nên khó "nuôi" tài khoản bằng giấy tờ của người khác.

### A3a. Kiểm tra "đã đăng ký chưa" bằng mã băm có khóa
- **Vấn đề:** muốn biết một số căn cước đã dùng chưa thì phải lưu nó. Nhưng lưu nguyên số căn cước thì một lần lộ dữ liệu sẽ lộ luôn danh sách định danh của khách hàng. Số căn cước chỉ có 12 chữ số, nên mã hóa đơn giản cũng dễ bị dò ngược.
- **Làm gì:** chỉ lưu một mã băm tính bằng khóa bí mật của máy chủ.
- **Giá trị:** vẫn phát hiện được thẻ dùng lại, nhưng kho dữ liệu có bị lấy cũng không đọc ra số căn cước.

### A4. Người dùng xác nhận thông tin
- **Vấn đề:** máy đọc QR có thể sai, người dùng có thể cố ý sửa để khai khác giấy tờ. Nếu không có bước này, lỗi lọt vào hồ sơ ngân hàng; nếu cấm sửa, người thật bị kẹt khi máy đọc nhầm.
- **Làm gì:** cho xem và xác nhận. Sửa vẫn được, nhưng hồ sơ được **gắn cờ** cho nhân viên xem.
- **Giá trị:** cân bằng giữa không làm khó người thật và không để khai man lọt qua lặng lẽ.

---

## Giai đoạn B · Có phải người thật, đúng người không

### B0. Chỉ đổi camera một lần (camera sau → camera trước, rồi giữ bật tới hết)
- **Vấn đề:** mỗi lần tắt mở hay đổi camera là một khe hở để tráo người, tráo nguồn hình. Người dùng cũng bị rối.
- **Làm gì:** camera sau chỉ cho căn cước; từ lúc chụp mặt, camera trước bật liên tục tới khi đọc xong câu.
- **Giá trị:** cả quá trình là một đoạn liền mạch của cùng một người, khó chen vào giữa.

### B1. Hướng dẫn chụp ngay trên điện thoại, tự bắt đầu
- **Vấn đề:** ảnh tối, mờ, xa làm AI chấm sai, và người thật bị bắt làm lại nhiều lần. Bắt người dùng tự bấm chụp thì họ thường bấm lúc chưa sẵn sàng.
- **Làm gì:** điện thoại nhắc ngay "hơi tối", "lại gần hơn", và tự bắt đầu khi đủ điều kiện. Điện thoại **chỉ hướng dẫn, không quyết định**.
- **Giá trị:** ảnh gửi lên tốt hơn ngay từ đầu, ít phải chụp lại, ít chấm oan người thật.

### B1a. Kiểm tra camera ảo (CamProbe)
- **Vấn đề:** cách rẻ nhất để vượt eKYC là dùng **camera ảo** hoặc can thiệp vào trình duyệt để phát video có sẵn thay cho camera thật. Nhìn hình thì không phân biệt được.
- **Làm gì:** đo các dấu hiệu bất thường của camera và trình duyệt, gửi lên máy chủ chấm.
- **Giá trị:** chặn sớm kiểu tấn công phổ biến và rẻ tiền nhất.

### B2. Việc 1: giữ đầu yên (góc 1 → nháy màu → chấm sáng)

**Ảnh chính diện chụp lúc nền còn xám**
- **Vấn đề:** khi màn hình nháy màu, da mặt bị nhuốm màu, làm việc so khuôn mặt với ảnh căn cước kém chính xác.
- **Làm gì:** chụp ảnh chính diện trong giây đầu, khi màn hình còn trung tính.
- **Giá trị:** có một ảnh sạch để so với căn cước, mà người dùng không phải làm thêm bước nào.

**Màn hình nháy màu ngẫu nhiên (lớp ánh sáng)**
- **Vấn đề:** ảnh in, màn hình phát lại hay hình chèn sẵn đều có ánh sáng "đóng băng" từ lúc được tạo ra. Chúng không thể phản ứng với ánh sáng đang chiếu lên ngay lúc này.
- **Làm gì:** màn hình chiếu chuỗi màu do máy chủ chọn ngẫu nhiên; máy chủ kiểm da có đổi màu theo đúng thứ tự, đúng thời điểm, đúng độ trễ không.
- **Giá trị:** bằng chứng vật lý rằng có một khuôn mặt thật ở trước màn hình **ngay lúc này**. Độ trễ bất thường còn là dấu hiệu của mặt ghép thời gian thực.

**Chấm sáng chạy, mắt đuổi theo (lớp ánh mắt)**
- **Vấn đề:** video quay sẵn hay quay lén chứa chuyển động của một lần khác, không thể biết trước một đường đi vừa được sinh ra.
- **Làm gì:** chấm sáng chạy theo đường do máy chủ chọn; máy chủ đo ánh mắt có bám theo không. Đầu giữ yên để đo mắt cho sạch.
- **Giá trị:** đây là "câu trả lời cho đề vừa ra" rõ ràng nhất, nhìn bằng mắt cũng hiểu.

### B3. Việc 2: quay trái, quay phải theo thứ tự ngẫu nhiên
- **Vấn đề:**
  - ảnh in hay màn hình nghiêng đi chỉ méo phẳng, không có chiều sâu như mặt thật;
  - chỉ có một ảnh chính diện thì mô hình chống giả bỏ sót các dấu vết lộ ra ở góc nghiêng;
  - thứ tự cố định (luôn trái rồi phải) thì kẻ gian quay sẵn được.
- **Làm gì:** người dùng quay theo mũi tên, thứ tự do máy chủ chọn, tạo ra **góc 2 và góc 3**.
- **Giá trị:** chứng minh khuôn mặt có chiều sâu 3D; có thêm hai góc cho AI chấm; giống quy trình ba góc mặt người dân đã quen ở ngân hàng.

### B4. Các mô hình AI ở máy chủ

**Chống ảnh in, màn hình (DINOv2)**
- **Vấn đề:** cách giả đơn giản nhất là giơ ảnh in hoặc điện thoại đang hiện ảnh nạn nhân trước camera.
- **Giá trị:** chặn tấn công "đặt trước camera". Mô hình được tinh chỉnh trên dữ liệu người Việt vì mô hình nước ngoài lọt nhiều khi gặp dữ liệu Việt.

**Chống mặt ghép (GenD)**
- **Vấn đề:** công cụ AI có thể dựng khuôn mặt của người khác lên mặt kẻ gian, trông rất thật bằng mắt thường.
- **Giá trị:** tìm dấu vết của khuôn mặt do máy tạo ra, trên cả ba góc mặt.

**So mặt với căn cước và giữa các góc (AdaFace)**
- **Vấn đề:** một người thật, đang có mặt thật, vẫn có thể **không phải chủ căn cước**. Ngoài ra, kẻ gian có thể tráo người giữa các bước.
- **Giá trị:** xác nhận người đang làm chính là người trên thẻ, và cả ba góc mặt là cùng một người.

### B5. Chấm giai đoạn B trong lúc người dùng đọc câu
- **Vấn đề:** nếu bắt người dùng ngồi chờ máy chủ chấm xong mới cho làm tiếp, người thật mất thời gian, dễ bỏ cuộc.
- **Làm gì:** máy chủ chấm ngầm song song; nghi rõ thì kết quả cuối vẫn là chuyển nhân viên duyệt.
- **Giá trị:** nhanh cho người thật mà không nới lỏng kiểm tra.

---

## Giai đoạn C · Có tự nguyện không

### C1. Đọc to một câu ngẫu nhiên
- **Vấn đề:**
  - khuôn mặt thật vẫn có thể bị **ép buộc** hoặc **lừa** để xác minh hộ;
  - một đoạn ghi âm có sẵn không thể nói đúng một câu vừa được sinh ra;
  - giọng có thể do AI tạo.
- **Làm gì:** người dùng đọc một câu ngẫu nhiên (có nội dung mục đích, ví dụ "xác nhận mở tài khoản"), camera vẫn bật.
- **Giá trị:** chứng minh người dùng **chủ động và biết mình đang làm gì**, chặn ghi âm phát lại, và cho thêm một kênh bằng chứng thứ hai ngoài khuôn mặt.

**Đúng câu (PhoWhisper):** câu đọc phải đúng câu vừa ra, nếu không thì có thể là ghi âm cũ.
**Không phải giọng AI (AntiDeepfake):** giọng nhân bản bằng AI có thể đọc đúng câu, nên phải kiểm riêng xem giọng có phải do máy tạo không.
**Khẩu hình khớp tiếng (SyncNet):** nếu tiếng và môi lệch nhau, có thể hình và tiếng đến từ hai nguồn khác nhau.
**Vẫn cùng khuôn mặt:** để chắc người đọc câu là người đã qua giai đoạn B, không phải người khác ngồi vào.

---

## Giai đoạn D · Quyết định

### D1. Điện thoại ký video theo phiên
- **Vấn đề:** video có thể bị chặn và thay giữa đường, hoặc một video của phiên cũ được gửi lại cho phiên mới.
- **Làm gì:** điện thoại ký lên dữ liệu bằng khóa nằm trong chip, kèm mã của đúng phiên đó.
- **Giá trị:** máy chủ biết dữ liệu không bị sửa và thuộc đúng phiên này. Video cũ, video quay lén đều không dùng lại được.

### D2. Máy chủ là trọng tài, điện thoại không quyết định
- **Vấn đề:** điện thoại nằm trong tay người dùng, có thể đã bị cài phần mềm gian lận. Nếu để điện thoại tự báo "đạt", kẻ gian chỉ cần sửa phần mềm là qua.
- **Làm gì:** mọi phán đoán chạy ở máy chủ, từ dữ liệu gốc.
- **Giá trị:** kẻ gian kiểm soát được điện thoại cũng không kiểm soát được kết quả.

### D3. Bộ quyết định (TrustRouter)
- **Vấn đề:**
  - mỗi mô hình chỉ thấy một khía cạnh; nhìn riêng lẻ dễ sai;
  - nếu một mô hình bị lỗi mà hệ thống coi như "không thấy gì bất thường", kẻ gian chỉ cần làm hỏng mô hình đó;
  - nếu gộp "ảnh xấu" chung với "nghi giả", người thật ở chỗ tối bị coi như kẻ gian.
- **Làm gì:**
  - gộp mọi kết quả theo một thứ tự kiểm tra cố định;
  - module lỗi thì **không bao giờ** tính là đạt;
  - tách riêng "chụp lại" (lý do chất lượng) khỏi "chuyển duyệt" (nghi ngờ).
- **Giá trị:** quyết định nhất quán, giải thích được, không có lối tắt cho kẻ gian, và không trừng phạt người thật vì ánh sáng kém.

### D4. Không tự từ chối, chuyển nhân viên khi nghi ngờ
- **Vấn đề:** AI có thể nhầm. Từ chối tự động thì người thật bị khóa oan mà không có ai xem lại.
- **Làm gì:** ca nghi ngờ chuyển cho nhân viên, kèm lý do và bằng chứng.
- **Giá trị:** con người là người quyết định cuối cùng với ca khó; AI lọc bớt, không phán xử thay.

### D5. Người dân không bao giờ thấy điểm số hay chữ "giả mạo"
- **Vấn đề:**
  - nói "bị nghi giả mạo" với một người thật là xúc phạm và gây hoảng;
  - cho kẻ gian thấy điểm số là chỉ cho họ cách chỉnh tới khi lọt.
- **Làm gì:** người dùng chỉ thấy "đạt", "chụp lại" (nói về ánh sáng, khoảng cách), "làm lại", hoặc "đang xác minh thêm".
- **Giá trị:** tôn trọng người thật và không giúp kẻ gian dò đường.

### D6. Ngân hàng nhận kết quả có chữ ký, không nhận dữ liệu sinh trắc
- **Vấn đề:** nếu kết quả gửi đi không có chữ ký, kẻ gian có thể làm giả một kết quả "đạt". Nếu ngân hàng giữ thêm ảnh mặt và giọng nói, mỗi ngân hàng lại là một kho dữ liệu nhạy cảm có thể bị lộ.
- **Làm gì:** ngân hàng nhận "đạt / đang xét duyệt" kèm danh tính và chữ ký; không nhận ảnh mặt, video, giọng nói, điểm số.
- **Giá trị:** ngân hàng tin được kết quả, và bớt đi một nơi giữ dữ liệu sinh trắc.

### D7. VeriClue báo "xác minh thành công", ngân hàng mới báo "mở tài khoản thành công"
- **Vấn đề:** ngân hàng còn có quy định riêng (danh sách hạn chế, hạn mức…). Nếu VeriClue báo "mở tài khoản thành công" trước, người dùng có thể nhận một thông báo sai.
- **Giá trị:** mỗi bên chỉ nói điều mình chịu trách nhiệm.

### D8. Khóa thiết bị (passkey) và mẫu khuôn mặt cho lần sau
- **Vấn đề:** nếu lần nào cũng phải làm lại toàn bộ như đăng ký, người dùng sẽ ngại; còn nếu lần sau chỉ hỏi mật khẩu, kẻ gian lấy được mật khẩu là xong.
- **Làm gì:** sau khi đạt, điện thoại tạo một khóa nằm trong chip; máy chủ lưu mẫu khuôn mặt (dãy số, không phải ảnh) đã mã hóa.
- **Giá trị:** lần xác thực sau nhanh hơn nhưng vẫn cần đúng thiết bị và đúng khuôn mặt.

---

## Bảo vệ dữ liệu

### E1. Mã hóa theo từng phiên, tự hủy sau 24 giờ
- **Vấn đề:** kho chứa video khuôn mặt là mục tiêu béo bở. Giữ càng lâu, càng nhiều, rủi ro càng lớn; xóa từng file thì dễ sót bản sao.
- **Làm gì:** mỗi phiên mã hóa bằng một khóa riêng; hết hạn thì hủy khóa, dữ liệu thành vô nghĩa. Ca đang xét duyệt được giữ tới khi xử lý xong.
- **Giá trị:** dữ liệu chỉ tồn tại đủ lâu để phục vụ đúng mục đích; bị lấy cũng không đọc được.

### E2. Kháng lượng tử cho đường truyền và chữ ký
- **Vấn đề:**
  - kẻ gian có thể **ghi lại đường truyền hôm nay** và chờ máy tính lượng tử để giải mã sau; mật khẩu thì đổi được, còn **khuôn mặt thì không**;
  - kết quả xác minh phải còn đáng tin sau nhiều năm lưu hồ sơ, trong khi chữ ký kiểu cũ có thể bị máy lượng tử làm giả.
- **Làm gì:** dùng thuật toán mã hóa và chữ ký theo chuẩn kháng lượng tử, kết hợp với chữ ký hiện tại.
- **Giá trị:** bảo vệ dữ liệu không đổi được của người dân trong dài hạn, và giữ giá trị của kết quả xác minh qua thời gian.

### E3. Giấy chứng nhận ZKP (hướng mở rộng)
- **Vấn đề:** mỗi dịch vụ đều giữ một bản ảnh căn cước và khuôn mặt. Mỗi bản là một chỗ có thể lộ, và dữ liệu lộ lại chính là nguyên liệu để chèn ảnh hay dựng clip giả.
- **Làm gì:** dịch vụ chỉ cần biết một sự thật ("đã xác minh", "trên 18 tuổi") thì nhận bằng chứng cho đúng điều đó, không nhận dữ liệu gốc.
- **Giá trị:** ít bản sao dữ liệu sinh trắc hơn, tức ít nguyên liệu cho kẻ gian hơn. Ngân hàng mở tài khoản vẫn nhận danh tính đầy đủ theo quy định; ZKP dành cho các dịch vụ khác.

---

## Nền tảng phía sau

### F1. Rà soát dữ liệu bằng mắt và tai trước khi huấn luyện
- **Vấn đề:** nếu dữ liệu ảnh thật và ảnh giả khác nhau ở những thứ vô nghĩa (kích thước file, độ phân giải, độ dài âm thanh), mô hình sẽ **học vẹt** các mẹo đó, đạt điểm cao trong phòng thí nghiệm rồi thất bại ngoài đời.
- **Giá trị:** mô hình học đúng dấu hiệu giả mạo, và con số đo được phản ánh đúng thực tế.

### F2. Tinh chỉnh trên dữ liệu người Việt
- **Vấn đề:** mô hình học chủ yếu trên khuôn mặt, giọng nói và công cụ giả mạo nước ngoài; gặp người Việt và giọng tiếng Việt thì lọt nhiều hoặc chấm oan nhiều.
- **Giá trị:** thu hẹp khoảng cách giữa phòng thí nghiệm nước ngoài và người dùng Việt Nam.

### F3. Chọn ngưỡng bằng thống kê, không bằng cảm tính
- **Vấn đề:** ngưỡng đặt tay thì không ai biết hệ thống thật sự để lọt bao nhiêu kẻ gian và chặn oan bao nhiêu người thật.
- **Giá trị:** ngân hàng biết rõ mức rủi ro mình chấp nhận, và có cơ sở để giải trình.
