"""Local human transcription review; model proposals remain separate from labels."""

import argparse
import json
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from recognition_data import write_json

PAGE = """<!doctype html><html lang="vi"><meta charset="utf-8">
<title>Duyệt chữ CCCD — VeriClue</title>
<style>body{font:16px system-ui;max-width:1100px;margin:30px auto;background:#f5f7fb;color:#172238}button,input,select{font:inherit;padding:10px;margin:5px}input{width:85%}img{max-width:100%;background:white;border:1px solid #b8c3d3}section{background:white;padding:20px;border-radius:12px;margin:16px 0}#status{color:#174f8b}#crop{min-height:64px;max-height:210px;object-fit:contain}#card{max-height:550px}label{display:block}</style>
<h1>Duyệt chữ trên CCCD</h1><p>Đọc ảnh trước khi xác nhận. Gợi ý OCR có thể sai. Chỉ xác nhận crop một dòng, đủ chữ; crop bị cắt hoặc không đọc chắc thì bỏ qua hoặc đánh dấu không dùng.</p>
<section><label>Tập dữ liệu <select id="split"><option>train</option><option>valid</option><option>test</option></select></label>
<button id="prev">Ảnh trước</button><button id="next">Ảnh tiếp</button><button id="missing">Đến crop chưa duyệt</button>
<p id="status"></p><p id="field"></p><img id="crop"><p id="proposal"></p><p id="alternative"></p>
<label>Nội dung chữ đúng<input id="text" autocomplete="off" spellcheck="false"></label>
<button id="copy">Chép gợi ý vào ô (chưa xác nhận)</button><button id="save">Tôi đã đối chiếu ảnh — lưu nhãn</button>
<button id="reject">Crop không đủ điều kiện — loại</button><p id="message"></p></section>
<details><summary>Xem ảnh thẻ nguồn</summary><img id="card"></details>
<script>
let rows=[],index=0,token='',current=null;
const el=id=>document.getElementById(id);
async function api(url,options){const r=await fetch(url,options);if(!r.ok)throw Error(await r.text());return r.json()}
async function show(){if(!rows.length){el('status').textContent='Không có crop';return}current=await api('/sample/'+rows[index]);el('status').textContent=`${index+1}/${rows.length} — ${current.review?.reviewed?'Đã duyệt':'Chưa duyệt'}`;el('field').textContent=current.field;el('crop').src='/crop/'+current.uid;el('card').src='/card/'+current.uid;el('proposal').textContent='Seq2Seq: '+(current.proposal?.text??'(chưa chạy dự đoán)');el('alternative').textContent='Transformer: '+(current.alternative?.text??'(chưa chạy dự đoán)');el('text').value=current.review?.text??'';el('message').textContent=''}
async function load(){const r=await api('/samples?split='+el('split').value);rows=r.ids;token=r.token;index=0;await show()}
async function save(usable){try{await api('/review/'+current.uid,{method:'POST',headers:{'Content-Type':'application/json','X-Review-Token':token},body:JSON.stringify({text:el('text').value,usable,reviewed:true})});index=Math.min(index+1,rows.length-1);await show();el('message').textContent='Đã lưu.'}catch(e){el('message').textContent=e.message}}
el('save').onclick=()=>save(true);el('reject').onclick=()=>save(false);el('copy').onclick=()=>{el('text').value=current.proposal?.text??''};
el('prev').onclick=()=>{index=Math.max(0,index-1);show()};el('next').onclick=()=>{index=Math.min(rows.length-1,index+1);show()};
el('missing').onclick=async()=>{const r=await api('/samples?split='+el('split').value);const next=rows.findIndex(uid=>!r.reviewed.includes(uid));if(next>=0){index=next;show()}else el('message').textContent='Đã duyệt hết tập này.'};el('split').onchange=load;
load().catch(e=>el('message').textContent=e.message);
</script></html>"""


class Review(BaseModel):
    text: str
    usable: bool
    reviewed: bool


def create_app(dataset):
    dataset = Path(dataset).resolve()
    rows = json.loads((dataset / "samples.json").read_text(encoding="utf-8"))
    by_id = {row["uid"]: row for row in rows}
    source_root = Path(
        json.loads((dataset / "dataset_info.json").read_text(encoding="utf-8"))["source_root"]
    ).resolve()
    reviews_path = dataset / "reviews.json"
    token = secrets.token_urlsafe(32)
    lock = threading.Lock()
    app = FastAPI(docs_url=None, redoc_url=None)

    def row_for(uid):
        if uid not in by_id:
            raise HTTPException(404, "Unknown sample")
        return by_id[uid]

    def load_reviews():
        return json.loads(reviews_path.read_text(encoding="utf-8"))

    def safe_file(root, relative):
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise HTTPException(404, "Image unavailable")
        return FileResponse(path)

    @app.get("/", response_class=HTMLResponse)
    def index():
        return PAGE

    @app.get("/samples")
    def samples(split: str = "train"):
        with lock:
            reviews = load_reviews()
        prediction_path = dataset / "predictions_seq2seq.json"
        proposals = (
            json.loads(prediction_path.read_text(encoding="utf-8"))
            if prediction_path.exists()
            else {}
        )
        ids = [r["uid"] for r in rows if r["split"] == split]
        ids.sort(key=lambda uid: uid not in proposals)
        return {
            "ids": ids,
            "token": token,
            "reviewed": [uid for uid, r in reviews.items() if r.get("reviewed")],
        }

    @app.get("/sample/{uid}")
    def sample(uid: str):
        row = row_for(uid)
        path = dataset / "predictions_seq2seq.json"
        predictions = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        alternative_path = dataset / "predictions_transformer.json"
        alternative = (
            json.loads(alternative_path.read_text(encoding="utf-8"))
            if alternative_path.exists()
            else {}
        )
        with lock:
            reviews = load_reviews()
        return {
            **row,
            "proposal": predictions.get(uid),
            "alternative": alternative.get(uid),
            "review": reviews.get(uid),
        }

    @app.get("/crop/{uid}")
    def crop(uid: str):
        return safe_file(dataset, row_for(uid)["crop"])

    @app.get("/card/{uid}")
    def card(uid: str):
        return safe_file(source_root, row_for(uid)["image"])

    @app.post("/review/{uid}")
    def save(uid: str, review: Review, x_review_token: str = Header(default="")):
        row_for(uid)
        if not secrets.compare_digest(x_review_token, token):
            raise HTTPException(403, "Invalid local review token")
        if not review.reviewed or (review.usable and not review.text.strip()):
            raise HTTPException(422, "Human confirmation and nonempty text required")
        if len(review.text) > 1024 or any(c in review.text for c in "\r\n\t"):
            raise HTTPException(422, "Expected one text line, max 1024 characters")
        with lock:
            reviews = load_reviews()
            value = {
                **review.model_dump(),
                "text": review.text.strip(),
                "reviewed_at": datetime.now(timezone.utc).isoformat(),  # noqa: UP017 -- lab Python 3.10
            }
            with (dataset / "review_history.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(
                    json.dumps(
                        {"uid": uid, "previous": reviews.get(uid), "new": value}, ensure_ascii=False
                    )
                    + "\n"
                )
            reviews[uid] = value
            write_json(reviews_path, reviews)
        return {"saved": True}

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8020)
    args = parser.parse_args()
    import uvicorn

    uvicorn.run(create_app(args.dataset), host="127.0.0.1", port=args.port)
