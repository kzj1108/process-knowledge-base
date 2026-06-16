# 用 GitHub + Render 发布工艺知识库（免费 .com 子域名）

Render 会给你一个地址，例如：

`https://process-knowledge-base.onrender.com`

也可在 Render 绑定你自己的 `.com` 域名（需在该域名 DNS 里配置 CNAME）。

---

## 一、准备 GitHub 仓库

### 1. 在 GitHub 新建仓库

例如：`process-knowledge-base`（空仓库即可）

### 2. 在本机上传代码

在 PowerShell 中（路径按你的实际修改）：

```powershell
cd C:\Users\86159\.cursor\projects\empty-window\digital-twin-machining

git init
git add .
git commit -m "Initial: process knowledge base for Render"
git branch -M main
git remote add origin https://github.com/你的用户名/process-knowledge-base.git
git push -u origin main
```

> 若没有安装 git：从 https://git-scm.com 安装后再执行。

---

## 二、在 Render 创建 Web 服务

1. 打开 https://render.com 注册/登录（可用 GitHub 登录）
2. 点击 **New +** → **Web Service**
3. 连接你的 GitHub 账号，选择刚推送的仓库
4. 配置如下（多数会自动读 `render.yaml`）：

| 项 | 值 |
|----|-----|
| Name | process-knowledge-base |
| Region | Singapore（国内访问稍好） |
| Branch | main |
| Runtime | **Docker**（必须，否则 STEP 无法解析） |
| Dockerfile Path | `./Dockerfile` |
| Build Command | （Docker 模式留空） |
| Start Command | （Docker 模式留空，由 Dockerfile CMD 启动） |
| Plan | Free |

5. **Environment Variables**（在 Render 面板添加，部署后查看生成的密码）：

| Key | 说明 |
|-----|------|
| `PKB_ADMIN_USER` | `admin` |
| `PKB_ADMIN_PASS` | 自己设强密码（Render 也可自动生成） |
| `PKB_API_KEY` | 自己设一长串随机字符 |

6. 点击 **Create Web Service**，等待 Build 完成（约 3～8 分钟）

7. 顶部出现 **URL**，点开即可，例如：  
   `https://process-knowledge-base.onrender.com`

8. 登录：你在环境变量里设的 `PKB_ADMIN_USER` / `PKB_ADMIN_PASS`

---

## 三、绑定你自己的 .com 域名（可选）

1. Render 服务页 → **Settings** → **Custom Domains**
2. 添加：`pkb.yourcompany.com`
3. 按提示在域名服务商添加 **CNAME** 记录指向 Render
4. 等待 SSL 自动签发（HTTPS）

大陆访问自定义域名时，若服务器在境外一般无需 ICP；若用国内 CDN 需按厂商要求备案。

---

## 四、免费版注意事项

| 问题 | 说明 |
|------|------|
| **冷启动** | 免费服务 15 分钟无访问会休眠，首次打开要等 30～60 秒 |
| **数据持久化** | 免费版重启/重新部署后 SQLite 可能清空；演示数据会在启动时自动 seed |
| **持久盘** | 需付费计划 + `render.yaml` 里 `disk` 配置 |
| **涉密数据** | 勿把真实军工工艺数据放在 Render 公网 |

---

## 五、用 Blueprint 一键部署（可选）

仓库根目录已有 `render.yaml` 时：

1. Render 控制台 → **New +** → **Blueprint**
2. 选择该 GitHub 仓库
3. 按提示设置 `PKB_ADMIN_PASS` 等变量
4. 部署完成即可获得 URL

---

## 六、更新网站

改代码后：

```powershell
git add .
git commit -m "update"
git push
```

Render 会自动重新构建部署。

---

## 七、Unity 连接 Render 地址

`StreamingAssets/twin_config.json`：

```json
{
  "apiBaseUrl": "https://process-knowledge-base.onrender.com",
  "equipmentCode": "CNC-01",
  "defaultPartNo": "PART-GEAR-001"
}
```

---

## 常见问题

**Build 失败 `list[float]`**  
Render 使用 Python 3.11 即可；确保 `render.yaml` 里 `PYTHON_VERSION: 3.11.9`。

**Build 失败 `cadquery` / `libGL`**  
确认 Runtime 为 **Docker**，且仓库根目录有 `Dockerfile`（内含 `libgl1` 与 `requirements-cad.txt`）。构建日志应出现 `cadquery ok`。

**502 / 启动失败**  
在 Render → Logs 查看日志；确认 Start Command 与仓库目录结构一致。

**想保留上传的数据**  
升级付费并启用 Persistent Disk，或后续改为 PostgreSQL。
