# Python FastAPI 服务启动与使用指南（Windows/Conda）

## 概述
- 服务入口：`b:\yolo_env\deepLearning\ultralytics-8.3.163\service\main.py`
- 运行环境：Windows + Conda 环境 `yolo`
- 默认端口：`8077`（可改为 `3000` 与前端对齐）
- 接口：`POST /detect` 与 `POST /api/detect`
- 功能：YOLO 推理，返回检测结果与带框图片路径（`labeledPath`）

## 目录位置
- 代码目录：`b:\yolo_env\deepLearning\ultralytics-8.3.163\service`
- 入口文件：`main.py`

## 环境要求
- Python 3.8+
- Conda 环境：`yolo`
- 依赖：`fastapi`、`uvicorn`、`pillow`、`opencv-python`、`ultralytics`（已在项目中使用）

## 安装依赖
```powershell
conda activate yolo
python -m pip install fastapi uvicorn pillow opencv-python
```

## 环境变量（建议设置）
- 作用说明：
  - `UPLOADS_BASE_DIR`：相对路径归一化的本地根（解析 `uploads/images/...`）
  - `UPLOADS_HTTP_BASE`：相对路径的 HTTP 根（从该地址下载为临时文件）
  - `LABELS_BASE_DIR`：保存带框图片的物理目录（用于前端访问与对比展示）

- PowerShell 设置：
```powershell
$env:UPLOADS_BASE_DIR = 'B:\yolo_env\deepLearning\foreignscan-windows'
$env:UPLOADS_HTTP_BASE = 'http://172.20.10.2:3000'
$env:LABELS_BASE_DIR = 'B:\yolo_env\deepLearning\foreignscan-backend\cmd\server\uploads\labels'
```

- CMD/Anaconda Prompt 设置：
```cmd
set "UPLOADS_BASE_DIR=B:\yolo_env\deepLearning\foreignscan-windows"
set "UPLOADS_HTTP_BASE=http://172.20.10.2:3000"
set "LABELS_BASE_DIR=B:\yolo_env\deepLearning\foreignscan-backend\cmd\server\uploads\labels"
```

## 启动命令
- PowerShell 或 CMD（推荐）：
```powershell
conda activate yolo
cd b:\yolo_env\deepLearning\ultralytics-8.3.163\service
python -m uvicorn main:app --host 0.0.0.0 --port 8077
```

- 开发模式（自动重载）：
```powershell
python -m uvicorn main:app --host 0.0.0.0 --port 8077 --reload
```

- 从项目根启动（不切目录）：
```powershell
python -m uvicorn ultralytics-8.3.163.service.main:app --host 0.0.0.0 --port 8077
```

- 端口对齐前端（可选）：
```powershell
python -m uvicorn main:app --host 0.0.0.0 --port 3000
```

## 接口说明
- 路由：
  - `POST /detect`
  - `POST /api/detect`（与 `/detect` 等价）

- 请求体（JSON）：
```json
{
  "image_path": "string",   // 必填：图片路径（HTTP 或相对路径 uploads/images/...）
  "model_path": "string",   // 可选：模型权重（默认 yolov8n.pt）
  "conf": 0.25,               // 可选：置信度阈值（默认 0.25）
  "iou": 0.5                  // 可选：IoU 阈值（默认 0.5）
}
```

- 响应体（JSON）：
```json
{
  "success": true,
  "items": [
    {
      "classId": 0,
      "class_": "person",
      "confidence": 0.93,
      "bbox": { "x": 345.4, "y": 356.4, "width": 685.1, "height": 706.3 }
    }
  ],
  "summary": { "hasIssue": false, "issueType": "", "objectCount": 1, "avgScore": 0.93 },
  "labeledPath": "uploads/labels/<sceneId>/<filename>.jpg" // 若成功生成带框图片
}
```

## 调用示例
- 传 HTTP 源图：
```powershell
$body = '{"image_path":"http://172.20.10.2:3000/uploads/images/<sceneId>/<filename>.jpg","conf":0.25,"iou":0.45}'
Invoke-WebRequest -Uri http://127.0.0.1:8077/detect -Method Post -Body $body -ContentType 'application/json'
```

- 传相对路径（需设置 `UPLOADS_HTTP_BASE` 或本地存在）：
```powershell
$body = '{"image_path":"uploads\\images\\<sceneId>\\<filename>.jpg","conf":0.25,"iou":0.45}'
Invoke-WebRequest -Uri http://127.0.0.1:8077/api/detect -Method Post -Body $body -ContentType 'application/json'
```

## 带框图片输出
- 物理保存目录：`LABELS_BASE_DIR/<sceneId>/<filename>.jpg`
- 响应体返回：`labeledPath`（相对路径 `uploads/labels/<sceneId>/<filename>.jpg`）
- 前端访问（通过 Go 静态映射）：`API_BASE + labeledPath`

## 常见问题
- 404 Not Found：检查请求路径是否为 `/detect` 或 `/api/detect`
- 400 Bad Request：检查 `image_path` 是否可访问（HTTP 可下载或本地存在）；设置 `UPLOADS_HTTP_BASE` 可支持相对路径下载
- 环境变量设置：PowerShell 用 `$env:VAR='value'`；CMD 用 `set VAR=value`
- Windows 路径规范：不要写成 `/b:/...`，使用 `B:\...` 或 `B:/...`

## 调试建议
- 查看路由文档：`http://127.0.0.1:8077/openapi.json`
- 打印返回 `detail` 字段以定位文件解析失败路径
- 在前端/网关中优先传绝对 HTTP 地址，减少本地路径差异
