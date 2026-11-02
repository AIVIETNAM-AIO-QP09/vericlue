"""Build a standalone review page from the exact offline Android scene sources."""

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ASSETS = ROOT / "apps/android/app/src/main/assets/three"
DEST = ROOT / "tmp/app11-ui/three"
DEST.mkdir(parents=True, exist_ok=True)
snapshots = ROOT / "apps/android/app/src/test/snapshots/images"
for name, suffix in {
    "auth": "02_auth",
    "terms": "03_terms",
    "face": "09_face_ready",
    "success": "18_success",
}.items():
    source = (
        snapshots
        / f"vn.vericlue.app.screenshots_CompactOnboardingJourneySnapshotTest_orderedJourney_{suffix}_light.png"
    )
    if source.exists():
        shutil.copy2(source, DEST / f"android-{name}.png")

payload = {
    key: (ASSETS / file).read_text(encoding="utf-8")
    for key, file in {
        "library": "vendor/three.module.min.js",
        "factory": "illustrations.js",
        "scene": "scene.js",
        "css": "scene.css",
    }.items()
}
PAGE = r"""<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>VeriClue · Trải nghiệm Three.js</title><style>
*{box-sizing:border-box}body{margin:0;background:#faf8f5;color:#14202b;font:16px/1.6 system-ui,sans-serif}
main{max-width:1120px;margin:auto;padding:40px 24px}h1{font-size:clamp(28px,4vw,44px);line-height:1.15;max-width:750px;margin:16px 0}
p{color:#5b6670;max-width:780px}.tag{font-size:12px;letter-spacing:2px;color:#0b5fa5}.grid{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(0,1fr);gap:32px}
section{min-width:0}h2{font-size:22px}.stage{border-radius:28px;background:#0c2345;padding:20px;border:1px solid #344a60;color:#fff}
.stage.light{background:#f0eee9;color:#14202b;border-color:#d4cfc5}.stage-head{display:flex;justify-content:space-between;align-items:center;gap:16px;font-size:13px;letter-spacing:1px}
iframe{display:block;width:100%;height:320px;border:0;pointer-events:none}.controls,.chapters{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0}
button{font:inherit;min-height:48px;padding:10px 16px;border-radius:16px;background:#fff;color:#0c2345;border:1px solid #a6afb6;cursor:pointer}
button:hover{border-color:#246bdf}button:focus-visible,a:focus-visible{outline:3px solid #246bdf;outline-offset:3px}
button[aria-pressed="true"],#replay{background:#0c2345;color:#fff;border-color:#0c2345}.small{font-size:14px}
.context{display:inline-block;border-radius:20px;background:#e5edf5;color:#174c77;padding:5px 12px;font-size:13px}
.native{background:#f2eee8;border-radius:28px;padding:20px}img.native-shot{display:block;width:100%;max-width:320px;border-radius:20px;margin:auto;border:1px solid #e0d9ce}
.note{font-size:14px}a{color:#0b5fa5}.gallery{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-top:32px}
.gallery button{padding:12px;background:#0c2345;color:#fff;border-color:#344a60}.gallery img{display:block;width:100%;height:125px;object-fit:contain}.gallery span{display:block;font-size:14px}
#status{min-height:26px}.stage button{background:transparent;color:inherit;border-color:#758ba4;font-size:13px;min-height:48px}
@media(max-width:760px){.grid{grid-template-columns:1fr}.gallery{grid-template-columns:repeat(2,minmax(0,1fr))}main{padding:24px 16px}iframe{height:280px}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto}}
</style><main><div class="tag">VERICLUE / ANDROID / THREE.JS</div>
<h1>Mỗi bước, một cách hiểu rõ hơn.</h1>
<p>Bảy cảnh 3D tự dựng, dùng ở bốn màn Android. Chọn từng mục để xem vật liệu, ánh sáng và chuyển động theo ngữ cảnh — cùng mã nguồn được đóng gói trong app.</p>
<div class="chapters" aria-label="Chọn cảnh minh họa" id="chapters"></div>
<div class="grid"><section><span id="context" class="context"></span><h2 id="title"></h2>
<div class="stage" id="stage"><div class="stage-head"><span>MINH HỌA 3D TRỰC TIẾP</span><button id="theme">Nền sáng</button></div>
<iframe id="preview" title="Cảnh Three.js minh họa"></iframe></div>
<p id="description"></p><div class="controls"><button id="replay">Xem lại chuyển động</button><button id="pause">Tạm dừng</button></div>
<p id="status" role="status" class="note">Đang nạp cảnh…</p>
<p class="note">Đổi mục trong cùng một renderer. Hướng dẫn có nút dừng/xem lại và chạy tối đa 6 giây; quyền riêng tư và hoàn tất chạy 3 giây. Sóng âm là minh họa, không thu micro. Cảnh khuôn mặt không phải thử thách xác minh thật.</p>
</section><section><h2>Vị trí trong app Android</h2><div class="native"><img id="native" class="native-shot" alt="Bố cục Android với hình dự phòng"></div>
<p id="native-note" class="note"></p><p class="note">Ảnh Compose thật dùng hình tĩnh dự phòng. Cảnh bên trái chạy WebGL trên trình duyệt, chưa phải bằng chứng WebView đã chạy trên điện thoại.</p></section></div>
<div class="gallery" id="gallery" aria-label="Bộ cảnh"></div>
<p class="note">Giảm chuyển động hoặc thiếu WebGL: Android dùng biểu tượng/hình native và giữ nguyên hướng dẫn, lựa chọn và nút tiếp tục.</p>
<p><a href="browser-results.json">Kết quả kiểm tra WebGL</a> · <a href="../upgrade/index.html">Xem các màn Android</a> · <a href="../index.html">So với giao diện ban đầu</a></p></main>
<script>const payload=PAYLOAD;
const items=[
 ['card','Thẻ căn cước','Màn bắt đầu','auth','Chuẩn bị thẻ thật, giữ trọn thẻ trong khung và tránh ánh sáng phản chiếu.'],
 ['face','Giữ thẳng','Màn bắt đầu / Chuẩn bị khuôn mặt','face','Mô hình đầu và khung hướng dẫn giúp hình dung vị trí điện thoại ngang tầm mắt.'],
 ['eyes','Đưa mắt','Chuẩn bị khuôn mặt','face','Đầu giữ yên, mắt di chuyển theo điểm minh họa. Khi xác minh, làm theo hướng dẫn thực tế.'],
 ['turn','Quay đầu','Chuẩn bị khuôn mặt','face','Xem chuyển động quay chậm rồi trở lại nhìn thẳng trước khi bắt đầu camera.'],
 ['voice','Giọng nói','Màn bắt đầu','auth','Micro và dải âm minh họa cho bước bổ sung. Chỉ đọc khi được yêu cầu; đây không phải ghi âm.'],
 ['privacy','Quyền riêng tư','Màn đồng ý dữ liệu','terms','Minh họa cho phần giải thích quyền chủ động. Đồng ý vẫn là lựa chọn riêng, không được chọn sẵn.'],
 ['success','Hoàn tất','Màn xác minh thành công','success','Huy hiệu nổi và các điểm sáng mở ra ngắn. Trong app, màn này chỉ xuất hiện theo kết quả của luồng xác minh.']
];
const url=source=>URL.createObjectURL(new Blob([source],{type:'text/javascript'}));
const libraryUrl=url(payload.library),factoryUrl=url(payload.factory.replace('./vendor/three.module.min.js',libraryUrl));
const sceneUrl=url(payload.scene.replace('./vendor/three.module.min.js',libraryUrl).replace('./illustrations.js',factoryUrl));
const preview=document.getElementById('preview'),statusText=document.getElementById('status');
let current='card',dark=true,paused=false,configured=false;
const controller=()=>preview.contentWindow?.vericlueScene;
function select(id){current=id;const item=items.find(x=>x[0]===id);document.getElementById('title').textContent=item[1];
 document.getElementById('context').textContent=item[2];document.getElementById('description').textContent=item[4];
 document.getElementById('native').src='android-'+item[3]+'.png';document.getElementById('native-note').textContent='Bố cục mặc định của màn: '+item[2]+'.';
 document.querySelectorAll('[data-scene]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.scene===id)));
 controller()?.configure(current,dark);}
items.forEach(([id,label])=>{const b=document.createElement('button');b.textContent=label;b.dataset.scene=id;b.onclick=()=>select(id);document.getElementById('chapters').appendChild(b);
 const g=document.createElement('button');g.dataset.scene=id;g.setAttribute('aria-label','Xem '+label);g.onclick=()=>select(id);
 const img=document.createElement('img');img.src=id+'-dark.png';img.alt='';const span=document.createElement('span');span.textContent=label;g.append(img,span);document.getElementById('gallery').appendChild(g);});
document.getElementById('theme').onclick=()=>{dark=!dark;document.getElementById('stage').classList.toggle('light',!dark);document.getElementById('theme').textContent=dark?'Nền sáng':'Nền tối';controller()?.configure(current,dark);};
document.getElementById('replay').onclick=()=>{paused=false;controller()?.setActive(true);controller()?.replay();document.getElementById('pause').textContent='Tạm dừng';};
document.getElementById('pause').onclick=()=>{paused=!paused;controller()?.setActive(!paused);document.getElementById('pause').textContent=paused?'Tiếp tục':'Tạm dừng';};
preview.srcdoc='<!doctype html><html lang="vi"><meta charset="utf-8"><style>'+payload.css+'</style><canvas id="scene" aria-hidden="true"></canvas><script type="module">import "'+sceneUrl+'";<'+ '/script></html>';
setInterval(()=>{const s=controller();if(!s)return;if(s.status==='ready'&&!configured){s.configure(current,dark);s.setActive(!paused);configured=true;}
 const message=s.status==='fallback'?'WebGL không khả dụng. Xem ảnh render trong bộ cảnh phía dưới.':s.playing?'Đang minh họa…':s.elapsed>=s.duration?'Đã hoàn tất chuyển động. Có thể xem lại hoặc chọn cảnh khác.':'Đang hiển thị tĩnh.';
 if(statusText.textContent!==message)statusText.textContent=message;},200);select('card');
</script></html>"""
(DEST / "index.html").write_text(
    PAGE.replace("PAYLOAD", json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")),
    encoding="utf-8",
)
print(DEST / "index.html")
