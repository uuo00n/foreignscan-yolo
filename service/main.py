from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from ultralytics import YOLO
import numpy as np
from pathlib import Path
import os
import tempfile
import urllib.request
import shutil
from urllib.parse import urlparse
import hashlib

app = FastAPI()

_models = {}

class BBox(BaseModel):
    x: float
    y: float
    width: float
    height: float

class Item(BaseModel):
    classId: int
    class_: str
    confidence: float
    bbox: BBox

class Summary(BaseModel):
    hasIssue: bool
    issueType: str
    objectCount: int
    avgScore: float

class DetectRequest(BaseModel):
    image_path: str
    model_path: Optional[str] = None
    conf: Optional[float] = 0.25
    iou: Optional[float] = 0.5

class DetectResponse(BaseModel):
    success: bool
    items: List[Item]
    summary: Summary
    labeledPath: Optional[str] = None

def _get_model(path: Optional[str]):
    # 强制使用指定模型，忽略传入的 yolov8s.pt 等默认值
    default_model = r"b:\yolo_env\deepLearning\ultralytics-8.3.163\service\best.pt"
    if not path or "yolov8" in path:
        key = default_model
    else:
        key = path
    m = _models.get(key)
    if m is None:
        m = YOLO(key)
        _models[key] = m
    return m

BASE_DIR = Path(os.environ.get("UPLOADS_BASE_DIR", r"B:\\yolo_env\\deepLearning\\foreignscan-windows"))
LABELS_BASE_DIR = Path(os.environ.get("LABELS_BASE_DIR", r"B:\\yolo_env\\deepLearning\\foreignscan-backend\\cmd\\server\\uploads\\labels"))

def normalize_path(p: str) -> str:
    if p.startswith("/") and len(p) > 2 and p[1].isalpha() and p[2] == ":":
        p = p[1:]
    q = Path(p)
    if not q.is_absolute():
        q = BASE_DIR / q
    return str(q.resolve())

def _download(url: str, suffix: str):
    fd, tmp = tempfile.mkstemp(suffix=suffix or ".tmp")
    os.close(fd)
    with urllib.request.urlopen(url) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f)
    return tmp

def resolve_source(p: str):
    s = p.strip()
    if s.lower().startswith("http://") or s.lower().startswith("https://"):
        tmp = _download(s, Path(s).suffix)
        return tmp, True
    q = Path(s)
    if not q.is_absolute():
        hb = os.environ.get("UPLOADS_HTTP_BASE", "").rstrip("/")
        if hb:
            url = f"{hb}/{q.as_posix()}"
            tmp = _download(url, q.suffix)
            return tmp, True
        path = normalize_path(s)
        if not Path(path).is_file() and hb:
            url = f"{hb}/{q.as_posix()}"
            tmp = _download(url, q.suffix)
            return tmp, True
        return path, False
    return str(q), False

def _extract_scene_and_filename(p: str):
    s = p.strip()
    if s.lower().startswith("http://") or s.lower().startswith("https://"):
        u = urlparse(s)
        parts = Path(u.path).parts
    else:
        parts = Path(s.replace("\\", "/")).parts
    try:
        i = parts.index("uploads")
        if i + 2 < len(parts) and parts[i + 1] == "images":
            scene = parts[i + 2]
            fname = parts[i + 3] if i + 3 < len(parts) else None
            if scene and fname:
                return scene, fname
    except ValueError:
        pass
    return None, None

def _save_labeled_image(r, dest_path: Path):
    try:
        from PIL import Image
        img = r.plot(conf=False)
        # r.plot() returns BGR, PIL expects RGB. Convert BGR to RGB.
        img = img[..., ::-1]
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(img).save(str(dest_path))
        return True
    except Exception:
        try:
            import cv2
            img = r.plot(conf=False)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            # r.plot() returns BGR, cv2.imwrite expects BGR. Save directly.
            cv2.imwrite(str(dest_path), img)
            return True
        except Exception:
            return False

def detect_impl(req: DetectRequest) -> DetectResponse:
    model = _get_model(req.model_path)
    source, cleanup = resolve_source(req.image_path)
    if not Path(source).is_file():
        raise HTTPException(status_code=400, detail=f"file not found: {source}")
    scene, fname = _extract_scene_and_filename(req.image_path)
    out_rel = None
    if scene and fname:
        out_rel = Path("uploads") / "labels" / scene / fname
    else:
        h = hashlib.sha1(req.image_path.encode("utf-8")).hexdigest()[:12]
        base = Path(source).name or "image.jpg"
        out_rel = Path("uploads") / "labels" / h / base
    out_abs = LABELS_BASE_DIR / Path(out_rel).parts[-2] / Path(out_rel).name if out_rel else None
    try:
        results = model.predict(source=source, conf=req.conf, iou=req.iou, verbose=False)
    finally:
        if cleanup:
            try:
                os.remove(source)
            except Exception:
                pass
    items: List[Item] = []
    names = model.names
    for r in results:
        if r.boxes is None:
            continue
        xywh = r.boxes.xywh.cpu().numpy() if hasattr(r.boxes, "xywh") else None
        cls = r.boxes.cls.cpu().numpy().astype(int) if hasattr(r.boxes, "cls") else None
        conf = r.boxes.conf.cpu().numpy() if hasattr(r.boxes, "conf") else None
        if xywh is None or cls is None or conf is None:
            continue
        for i in range(xywh.shape[0]):
            x, y, w, h = xywh[i].tolist()
            cid = int(cls[i])
            score = float(conf[i])
            cname = names[cid] if names and cid in names else str(cid)
            items.append(Item(classId=cid, class_=cname, confidence=score, bbox=BBox(x=x, y=y, width=w, height=h)))
    if len(results) > 0 and out_abs is not None:
        _save_labeled_image(results[0], out_abs)
    count = len(items)
    avg = float(np.mean([it.confidence for it in items])) if count > 0 else 0.0
    summary = Summary(hasIssue=False, issueType="", objectCount=count, avgScore=avg)
    return DetectResponse(success=True, items=items, summary=summary, labeledPath=str(out_rel).replace("\\", "/") if out_rel else None)

@app.post("/api/detect", response_model=DetectResponse)
def detect_api(req: DetectRequest):
    return detect_impl(req)

@app.post("/detect", response_model=DetectResponse)
def detect_legacy(req: DetectRequest):
    return detect_impl(req)
