#!/usr/bin/env python3
"""从本机向已部署的 Render 站点导入 3000 条数据。

用法:
  python seed_3000_remote.py --url https://你的服务.onrender.com --api-key 你的PKB_API_KEY
"""
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True, help="站点根地址，如 https://xxx.onrender.com")
    p.add_argument("--api-key", required=True, help="Render 环境变量 PKB_API_KEY")
    p.add_argument("--total", type=int, default=3000)
    args = p.parse_args()

    base = args.url.rstrip("/")
    req = urllib.request.Request(
        f"{base}/api/v1/import/seed-bulk?total={args.total}",
        data=b"{}",
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-API-Key": args.api_key,
        },
    )
    print(f"POST {req.full_url}")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode())
            print(json.dumps(body, ensure_ascii=False, indent=2))
    except urllib.error.HTTPError as e:
        print(e.read().decode())
        raise SystemExit(1) from e


if __name__ == "__main__":
    main()
