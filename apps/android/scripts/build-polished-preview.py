"""Collect unedited native renders and APNGs into the local APP-11 review gallery."""

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEST = ROOT / "tmp/app11-ui/polished"
BASELINE = ROOT / "tmp/app11-ui/refined"
SNAPSHOTS = ROOT / "apps/android/app/src/test/snapshots"
PREFIX = "vn.vericlue.app.screenshots_CompactOnboardingJourneySnapshotTest_orderedJourney_"
VIEWPORT = "vn.vericlue.app.screenshots_CompactFaceViewportSnapshotTest_cameraAndGuideDoNotJumpBetweenPhases_"
SCENES = (
    ("auth", "Xác minh danh tính", "02_auth", None),
    ("ready", "Chuẩn bị khuôn mặt", "09_face_ready", None),
    ("framing", "Căn khuôn mặt", None, 0),
    ("baseline", "Giữ yên", None, 1),
    ("colour", "Đổi màu", None, 2),
    ("gaze", "Theo dõi điểm hướng dẫn", None, 4),
    ("left", "Quay trái", None, 6),
    ("right", "Quay phải", None, 7),
    ("center", "Nhìn thẳng", None, 8),
)
MOTIONS = (
    ("left", "Quay trái", "demonstrateLeftThenHold_head_left_true"),
    ("right", "Quay phải", "demonstrateRightThenHold_head_right_false"),
    ("center", "Trở về chính diện", "demonstrateReturnToCenterThenHold_head_null_true"),
)
FEEDBACK = ((3, "Quay thêm"), (5, "Chỉnh hướng"), (7, "Giữ tư thế"), (9, "Đưa mặt vào khung"))


def save_baseline() -> None:
    """Preserve the previous a373e88 renders before any gallery is refreshed."""
    DEST.mkdir(parents=True, exist_ok=True)
    for key, *_ in SCENES:
        source = BASELINE / f"{key}-after.png"
        target = DEST / f"{key}-before.png"
        if source.exists() and not target.exists():
            shutil.copy2(source, target)


def build() -> None:
    save_baseline()
    scenes = []
    for key, title, suffix, phase in SCENES:
        filename = f"{PREFIX}{suffix}_light.png" if suffix else f"{VIEWPORT}phase_{phase}.png"
        source = SNAPSHOTS / "images" / filename
        if source.exists():
            shutil.copy2(source, DEST / f"{key}-after.png")
        scenes.append(
            {
                "key": key,
                "title": title,
                "before": (DEST / f"{key}-before.png").exists(),
                "after": source.exists(),
            }
        )
    motions = []
    for key, title, suffix in MOTIONS:
        source = (
            SNAPSHOTS
            / "videos"
            / f"vn.vericlue.app.screenshots_HeadMotionGuideSnapshotTest_{suffix}.png"
        )
        if source.exists():
            shutil.copy2(source, DEST / f"motion-{key}.png")
        motions.append({"key": key, "title": title, "available": source.exists()})
    feedback = []
    for index, title in FEEDBACK:
        source = (
            SNAPSHOTS
            / "images"
            / (
                "vn.vericlue.app.screenshots_CompactHeadFeedbackSnapshotTest_"
                f"correctionsStayReadableAndKeepTheirFootprint_feedback_{index}.png"
            )
        )
        if source.exists():
            filename = f"feedback-{index}.png"
            shutil.copy2(source, DEST / filename)
            feedback.append({"title": title, "file": filename})
    payload = json.dumps(
        {"scenes": scenes, "motions": motions, "feedback": feedback}, ensure_ascii=False
    )
    (DEST / "index.html").write_text(PAGE.replace("PAYLOAD", payload), encoding="utf-8")
    print(
        f"{DEST / 'index.html'} ({len(scenes)} scenes; {sum(m['available'] for m in motions)} APNGs)"
    )


PAGE = r"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>VeriClue · Hoàn thiện trải nghiệm xác minh</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#faf8f5;color:#14202b;font:16px/1.6 system-ui,sans-serif}
main{max-width:1120px;margin:auto;padding:40px 24px}h1{font-size:clamp(28px,4vw,42px);line-height:1.2;margin:12px 0 20px;max-width:850px;text-wrap:balance}
h2{font-size:24px;line-height:1.3;margin:32px 0 12px}p{max-width:900px;color:#5b6670}.eyebrow{font-size:12px;letter-spacing:1.6px;font-weight:700;color:#0b5fa5}
.changes{display:flex;gap:8px;flex-wrap:wrap;margin:24px 0}.changes span{padding:8px 14px;background:#e8eef4;border-radius:12px;font-size:14px;color:#174c77}
nav,.motion-controls{display:flex;gap:8px;flex-wrap:wrap;margin:20px 0}button{font:inherit;min-height:48px;border:1px solid #a6afb6;border-radius:14px;padding:10px 16px;color:#0c2345;background:white;cursor:pointer}
button:hover{border-color:#0b5fa5;background:#f1f5f8}button[aria-pressed=true]{background:#0c2345;color:white;border-color:#0c2345}
button:focus-visible,a:focus-visible{outline:3px solid #246bdf;outline-offset:3px}.pair{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}
figure{margin:0;min-width:0;border:1px solid #ece7e0;background:white;padding:20px;border-radius:24px}figcaption{font-weight:650;margin-bottom:16px}
.pair img{display:block;max-width:375px;width:100%;height:auto;margin:auto;border-radius:16px}.missing{padding:24px;border:1px dashed #a6afb6;border-radius:16px}
.feedback-gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,220px),1fr));gap:16px}.feedback-gallery img{width:100%;height:auto;display:block}
.motion-stage{min-height:150px;display:flex;align-items:center;justify-content:center;background:#0e1822;border-radius:24px;padding:20px;color:white}
.motion-stage img{display:block;max-width:320px;width:100%;height:auto;border-radius:16px}.motion-stage p{color:#b7c7d6;margin:0}
.note{font-size:14px}a{color:#0b5fa5}footer{margin-top:32px;padding-top:24px;border-top:1px solid #ece7e0}
@media(max-width:640px){main{padding:24px 16px}.pair{grid-template-columns:1fr}figure{padding:16px}button{padding:10px 12px}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto}}
</style></head><body><main>
<div class="eyebrow">VERICLUE / ANDROID / APP-11</div>
<h1>Giao diện gọn hơn. Hướng dẫn rõ hơn.</h1>
<p>Đối chiếu màn hình Android trước và sau chỉnh sửa. Ảnh được render trực tiếp từ Compose; camera dùng dữ liệu tổng hợp, vùng Three.js dùng hình dự phòng native.</p>
<div class="changes"><span>Khung mặt rộng hơn</span><span>Hướng dẫn quay đầu có chuyển động</span><span>Kiểm tra tư thế trước khi tiếp tục</span></div>
<nav id="scenes" aria-label="Chọn màn hình đối chiếu"></nav>
<div class="pair"><figure><figcaption>Trước · a373e88</figcaption><div id="before"></div></figure>
<figure><figcaption>Sau · bản hoàn thiện</figcaption><div id="after"></div></figure></div>
<p class="note" id="caption" aria-live="polite"></p>
<h2>Chuyển động hướng dẫn quay đầu</h2>
<p>APNG ghi lại chuyển động native: xoay chậm, giữ tư thế và trở về chính diện. Chọn một hướng để xem; trang này không mở camera.</p>
<div class="motion-controls" id="motions" aria-label="Xem chuyển động native"></div>
<div class="motion-stage" id="motion-stage"><p>Chọn hướng để xem chuyển động.</p></div>
<p class="note">APNG có thể lặp khi trình duyệt phát lại. Trong app, minh họa xoay một lượt rồi giữ yên; chế độ giảm chuyển động dùng tư thế tĩnh. Thanh giữ tư thế lấy từ quan sát khuôn mặt, không biểu thị kết quả xác minh.</p>
<h2>Điều kiện tiếp tục</h2>
<div class="feedback-gallery" id="feedback-gallery" aria-label="Gợi ý chỉnh tư thế ngay tại chỗ"></div>
<p>App cần quan sát đủ khuôn mặt và tư thế quay đầu được yêu cầu. Phiên mới dùng hướng dẫn thích ứng: quay sai được nhắc ngay tại bước hiện tại, chỉ chuyển khi giữ đúng tư thế. Tổng lượt thu tối đa 30 giây theo server; phiên cũ giữ lịch cũ. Kiểm tra layout và mô phỏng chưa thay thế nghiệm thu camera hoặc chất lượng xác minh trên điện thoại.</p>
<footer><a href="../three/index.html">Xem bộ cảnh Three.js</a> · <a href="../index.html">Toàn bộ hành trình</a> · <a href="../refined/index.html">Lượt chỉnh sửa trước</a></footer>
</main><script>
const data=PAYLOAD;
data.feedback.forEach(item=>{const figure=document.createElement('figure'),caption=document.createElement('figcaption'),img=new Image();caption.textContent=item.title;img.src=item.file;img.alt=item.title+' · gợi ý native trong cùng bước quay đầu';figure.append(caption,img);document.getElementById('feedback-gallery').append(figure);});
function show(scene){
 document.querySelectorAll('#scenes button').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.key===scene.key)));
 for(const side of ['before','after']){
  const box=document.getElementById(side);box.replaceChildren();
  if(!scene[side]){const message=document.createElement('p');message.className='missing';message.textContent='Chưa có ảnh render. Chạy Paparazzi rồi tạo lại trang preview.';box.append(message);continue;}
  const img=new Image();img.src=scene.key+'-'+side+'.png';img.alt=scene.title+' · '+(side==='before'?'Trước chỉnh sửa':'Sau chỉnh sửa');box.append(img);
 }
 document.getElementById('caption').textContent=scene.title+' · ảnh native, dữ liệu minh họa.';
}
data.scenes.forEach(scene=>{const button=document.createElement('button');button.type='button';button.dataset.key=scene.key;button.textContent=scene.title;button.onclick=()=>show(scene);document.getElementById('scenes').append(button);});
document.getElementById('scenes').addEventListener('keydown',event=>{
 if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
 const buttons=[...document.querySelectorAll('#scenes button')],current=buttons.indexOf(document.activeElement);if(current<0)return;
 event.preventDefault();let index=event.key==='Home'?0:event.key==='End'?buttons.length-1:(current+(event.key==='ArrowRight'?1:-1)+buttons.length)%buttons.length;
 buttons[index].focus();buttons[index].click();
});
data.motions.forEach(motion=>{const button=document.createElement('button');button.type='button';button.textContent=motion.title;button.setAttribute('aria-pressed','false');button.onclick=()=>{
 document.querySelectorAll('#motions button').forEach(item=>item.setAttribute('aria-pressed',String(item===button)));
 const stage=document.getElementById('motion-stage');stage.replaceChildren();
 if(motion.available){const img=new Image();img.src='motion-'+motion.key+'.png';img.alt='Chuyển động native: '+motion.title;stage.append(img);}
 else{const message=document.createElement('p');message.textContent='Chưa có APNG. Chạy HeadMotionGuideSnapshotTest rồi tạo lại preview.';stage.append(message);}
};document.getElementById('motions').append(button);});
show(data.scenes[0]);
</script></body></html>"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--save-baseline", action="store_true", help="Preserve a373e88 renders only."
    )
    if parser.parse_args().save_baseline:
        save_baseline()
        print(f"Baseline preserved at {DEST}")
    else:
        build()
