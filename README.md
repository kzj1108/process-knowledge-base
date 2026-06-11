# 工艺知识库 Process Knowledge Base

数控滚齿加工单元工艺知识库（**实施方案5** 对齐版 v1.2.0），支持 Render + GitHub 部署。

## 功能（对应实施方案5 模块）

| 模块 | 接口/页面 |
|------|-----------|
| 4.1 综合看板 | `GET /api/v1/overview`、Web「综合看板」 |
| 4.2 基础数据 | 零件、设备、资源 `GET /api/v1/resources` |
| 4.3 工艺流程 | `GET /api/v1/process/static`、Web「工艺流程」 |
| 4.4 工艺知识 | `GET /api/v1/knowledge`、Web「工艺知识」 |
| 4.5 方案推荐 | `POST /api/v1/recommendations/process` |
| 4.6 设备工况 | `POST /api/v1/machining/realtime` |
| 4.7 质量追溯 | `POST/GET /api/v1/quality-records`、Web「质量追溯」 |
| 4.8 数据导入 | `POST /api/v1/import/csv/{kind}`、`GET /api/v1/import/template/{kind}` |
| 4.9 平台对接 | `GET /api/v1/integration/catalog`、Web「平台对接」、`/docs` |
| 4.10 安全审计 | `GET /api/v1/audit` |

首次启动（空库）自动写入 **GH-2024-088** 等演示数据，便于 Render 汇报。

## 本地运行

```bash
cd process-knowledge-base
pip install -r requirements.txt
export PKB_API_KEY=dev-test-key
uvicorn backend.main:app --reload --port 8090
```

浏览器打开 `http://127.0.0.1:8090`，管理台填写 API Key `dev-test-key`。

## Render 部署

1. 推送本目录到 GitHub
2. Render New Web Service → 连接仓库
3. 使用 `render.yaml`（或 Build: `pip install -r requirements.txt`，Start: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`）
4. 在 Render 控制台查看自动生成的 `PKB_API_KEY`，填入前端 API Key 输入框

> 公网演示仅用于汇报；正式军工环境请按实施方案部署内网达梦，勿将真实工艺放 Render。

## 环境变量

| 变量 | 说明 |
|------|------|
| PKB_API_KEY | 接口密钥（必填） |
| PKB_DB_DRIVER | sqlite（Render）/ dm（内网） |
| PKB_TARGET_TOTAL | 目标条数，默认 50000 |
| PKB_ADMIN_USER / PKB_ADMIN_PASS | 管理账号（预留） |

## 工艺推荐示例

```bash
curl -X POST https://your-app.onrender.com/api/v1/recommendations/process \
  -H "X-API-Key: YOUR_KEY" -H "Content-Type: application/json" \
  -d '{"material":"20CrMnTi","module_m":3,"teeth_z":42,"accuracy_grade":"6级","heat_treatment":"渗碳淬火"}'
```
