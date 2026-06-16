from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/integration", tags=["平台对接"])


@router.get("/catalog")
async def integration_catalog() -> Dict[str, Any]:
    endpoints: List[Dict[str, str]] = [
        {"code": "INT-01", "method": "POST", "path": "/api/v1/parts", "desc": "同步零件主数据"},
        {"code": "INT-02", "method": "POST", "path": "/api/v1/process/static", "desc": "新增工序工艺"},
        {"code": "INT-03", "method": "GET", "path": "/api/v1/process/static", "desc": "按零件查询工艺"},
        {"code": "INT-04", "method": "GET", "path": "/api/v1/knowledge", "desc": "查询工艺知识"},
        {"code": "INT-05", "method": "POST", "path": "/api/v1/machining/realtime", "desc": "上报设备工况"},
        {"code": "INT-06", "method": "POST", "path": "/api/v1/optimization/suggest-and-save", "desc": "优化结果回写"},
        {"code": "INT-07", "method": "GET", "path": "/api/v1/process/optimized/latest", "desc": "最新优化参数"},
        {"code": "INT-08", "method": "POST", "path": "/api/v1/import/csv/{kind}", "desc": "CSV 批量导入"},
        {"code": "INT-09", "method": "GET", "path": "/api/v1/audit", "desc": "审计日志"},
        {"code": "INT-10", "method": "GET", "path": "/health", "desc": "健康检查"},
        {"code": "INT-11", "method": "POST", "path": "/api/v1/recommendations/process", "desc": "工艺方案推荐"},
        {"code": "INT-12", "method": "POST", "path": "/api/v1/quality-records", "desc": "质量记录同步"},
        {"code": "INT-13", "method": "POST", "path": "/api/v1/recommendations/from-model", "desc": "三维模型→多条工艺路线推荐"},
        {"code": "INT-14", "method": "POST", "path": "/api/v1/recommendations/from-model", "desc": "含工艺路线图 SVG/HTML 导出"},
    ]
    return {
        "platform_name": "数控滚齿加工单元工艺知识库",
        "version": "2.1.0",
        "protocol": "HTTPS + JSON",
        "auth_header": "X-API-Key",
        "openapi_docs": "/docs",
        "endpoints": endpoints,
    }
