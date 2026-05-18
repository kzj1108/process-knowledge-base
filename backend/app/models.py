from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

KnowledgeCategory = Literal["RULE", "FAQ", "CASE", "STANDARD"]
KnowledgeStatus = Literal["DRAFT", "PUBLISHED", "ARCHIVED"]
EquipmentType = Literal["CNC", "ROBOT", "LINE"]


class LoginIn(BaseModel):
    username: str
    password: str


class PartCatalogIn(BaseModel):
    part_no: str
    part_name: str
    material: Optional[str] = None
    drawing_no: Optional[str] = None
    category: Optional[str] = None
    remark: Optional[str] = None


class PartCatalogUpdate(BaseModel):
    part_name: Optional[str] = None
    material: Optional[str] = None
    drawing_no: Optional[str] = None
    category: Optional[str] = None
    remark: Optional[str] = None


class EquipmentIn(BaseModel):
    code: str
    name: str
    type: EquipmentType
    model: Optional[str] = None
    workshop: Optional[str] = None
    status: str = "ACTIVE"


class EquipmentUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[EquipmentType] = None
    model: Optional[str] = None
    workshop: Optional[str] = None
    status: Optional[str] = None


class PartProcessIn(BaseModel):
    part_no: str
    part_name: Optional[str] = None
    material: Optional[str] = None
    operation_no: int
    operation_name: str
    equipment_code: Optional[str] = None
    tool_code: Optional[str] = None
    spindle_speed: Optional[float] = None
    cutting_depth: Optional[float] = None
    feed_rate: Optional[float] = None
    speed_min: Optional[float] = None
    speed_max: Optional[float] = None
    depth_min: Optional[float] = None
    depth_max: Optional[float] = None
    feed_min: Optional[float] = None
    feed_max: Optional[float] = None
    version: str = "1.0"
    approved_by: Optional[str] = None
    remark: Optional[str] = None


class PartProcessUpdate(BaseModel):
    part_name: Optional[str] = None
    material: Optional[str] = None
    operation_name: Optional[str] = None
    equipment_code: Optional[str] = None
    tool_code: Optional[str] = None
    spindle_speed: Optional[float] = None
    cutting_depth: Optional[float] = None
    feed_rate: Optional[float] = None
    speed_min: Optional[float] = None
    speed_max: Optional[float] = None
    depth_min: Optional[float] = None
    depth_max: Optional[float] = None
    feed_min: Optional[float] = None
    feed_max: Optional[float] = None
    is_active: Optional[bool] = None
    approved_by: Optional[str] = None
    remark: Optional[str] = None


class KnowledgeIn(BaseModel):
    category: KnowledgeCategory
    title: str = Field(min_length=1, max_length=256)
    content: str = Field(min_length=1)
    tags: Optional[str] = None
    related_part_no: Optional[str] = None
    related_op_no: Optional[int] = None
    source: Optional[str] = None
    author: Optional[str] = None
    status: KnowledgeStatus = "PUBLISHED"


class KnowledgeUpdate(BaseModel):
    category: Optional[KnowledgeCategory] = None
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[str] = None
    related_part_no: Optional[str] = None
    related_op_no: Optional[int] = None
    source: Optional[str] = None
    author: Optional[str] = None
    status: Optional[KnowledgeStatus] = None


class RealtimeIn(BaseModel):
    equipment_code: str
    part_no: Optional[str] = None
    ts: Optional[datetime] = None
    spindle_speed: Optional[float] = None
    cutting_depth: Optional[float] = None
    feed_rate: Optional[float] = None
    axis_x: Optional[float] = None
    axis_y: Optional[float] = None
    axis_z: Optional[float] = None
    joint_angles: Optional[List[float]] = None
    program_no: Optional[str] = None
    status: str = "RUN"
    raw_payload: Optional[Dict[str, Any]] = None


class OptimizationIn(BaseModel):
    equipment_code: str
    part_no: Optional[str] = None
    operation_no: Optional[int] = None
    input_snapshot: Optional[Dict[str, Any]] = None
    pred_spindle: float
    pred_depth: float
    pred_feed: float
    model_version: str = "v1"
    score: Optional[float] = None
    adopted: bool = False
    remark: Optional[str] = None


class ProcessQuery(BaseModel):
    part_no: str
    operation_no: Optional[int] = None
