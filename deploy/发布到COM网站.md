# 把工艺知识库发布到 .com 网站（公网域名访问）

目标：用户打开 `https://你的域名.com` 即可使用（不再只是 127.0.0.1）。

---

## 你需要准备的三样东西

| 项目 | 说明 |
|------|------|
| **域名** | 在阿里云 / 腾讯云 / GoDaddy 等购买，例如 `yourcompany.com` |
| **云服务器** | 1 核 2G 即可，公网 IP，系统推荐 Ubuntu 22.04 |
| **备案（仅中国大陆服务器）** | 服务器在大陆必须 ICP 备案，域名才能正常解析访问 |

军工/内网项目若不能上公网，请用内网域名 + 专线，步骤类似，只是不做公网备案。

---

## 方案 A：云服务器 + Docker（推荐）

### 1. 购买并登录服务器

```bash
ssh root@你的服务器公网IP
```

### 2. 安装 Docker

```bash
curl -fsSL https://get.docker.com | sh
apt install -y docker-compose-plugin
```

### 3. 上传项目

把本机整个 `digital-twin-machining` 文件夹上传到服务器，例如：

`/opt/digital-twin-machining`

（可用 WinSCP、FileZilla，或 `scp -r`）

### 4. 修改域名

编辑 `deploy/nginx.conf`，把：

```
server_name your-domain.com www.your-domain.com;
```

改成你的真实域名，例如：

```
server_name processkb.yourcompany.com;
```

### 5. 设置强密码并启动

```bash
cd /opt/digital-twin-machining/deploy
export PKB_ADMIN_PASS='你的强密码'
export PKB_API_KEY='随机长字符串'
docker compose up -d --build
```

### 6. 域名解析（DNS）

在域名控制台添加 **A 记录**：

| 主机记录 | 记录类型 | 值 |
|---------|---------|-----|
| `@` 或 `www` 或 `pkb` | A | 服务器公网 IP |

等待 5～30 分钟生效后，浏览器访问：

`http://你的域名.com`

### 7. 配置 HTTPS（强烈建议）

在服务器安装 certbot：

```bash
apt install -y certbot
certbot certonly --standalone -d 你的域名.com -d www.你的域名.com
```

把证书复制到项目：

```bash
mkdir -p /opt/digital-twin-machining/deploy/ssl
cp /etc/letsencrypt/live/你的域名.com/fullchain.pem deploy/ssl/
cp /etc/letsencrypt/live/你的域名.com/privkey.pem deploy/ssl/
```

取消 `nginx.conf` 里 HTTPS `server { ... }` 块的注释，并注释掉仅 HTTP 的 server 块，然后：

```bash
docker compose restart nginx
```

即可用：**https://你的域名.com**

---

## 方案 B：不用 Docker，直接跑 Python（简单）

服务器上：

```bash
cd /opt/digital-twin-machining/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PKB_ADMIN_PASS='强密码'
export PKB_API_KEY='随机key'
export PKB_DB_PATH=/opt/digital-twin-machining/database/process_kb.db
nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8090 &
```

再用 Nginx 反代 80/443 → `127.0.0.1:8090`（配置同 `deploy/nginx.conf`，`proxy_pass` 改为 `http://127.0.0.1:8090`）。

---

## 方案 C：临时演示用隧道（无服务器、有 .com 跳转）

仅用于演示，**不适合生产/涉密数据**：

- **Cloudflare Tunnel** / **ngrok**：把本机 8090 映射到临时域名  
- 正式 .com 仍需方案 A/B

---

## 登录与安全（上线必做）

1. 修改 `PKB_ADMIN_PASS`、`PKB_API_KEY` 环境变量  
2. 仅使用 **HTTPS**  
3. 防火墙只开放 80、443，**不要**对公网直接暴露 8090  
4. 涉密项目禁止把真实工艺数据放在公网未授权服务器  

---

## 常见问题

**Q：打开 .com 显示无法访问？**  
- 检查 DNS 是否指向正确 IP  
- 大陆服务器是否已备案  
- 安全组是否放行 80/443  

**Q：想让别人只读、不能改数据？**  
- 只分享浏览地址；写操作需要 API Key，不要泄露  

**Q：Unity 怎么连 .com？**  
- 修改 `StreamingAssets/twin_config.json`：  
  `"apiBaseUrl": "https://你的域名.com"`

---

## 本仓库一键文件

| 文件 | 用途 |
|------|------|
| `deploy/Dockerfile` | 应用镜像 |
| `deploy/docker-compose.yml` | 应用 + Nginx |
| `deploy/nginx.conf` | 域名反代 |
| `打开工艺知识库.bat` | 仅本机开发用 |

公网 .com 请用本说明 **方案 A** 在云服务器部署。
