-- Rich demo data for process knowledge base

INSERT OR IGNORE INTO part_catalog (part_no, part_name, material, drawing_no, category, remark) VALUES
('PART-GEAR-001', '传动齿轮', '40Cr', 'DW-G-001', '齿轮件', '模数 m=3'),
('PART-GEAR-002', '从动齿轮', '20CrMnTi', 'DW-G-002', '齿轮件', '渗碳淬火'),
('PART-SHAFT-002', '传动轴', '45钢', 'DW-S-002', '轴类件', '阶梯轴'),
('PART-HOUSING-003', '箱体端盖', 'HT250', 'DW-H-003', '箱体件', '铸铁件'),
('PART-BRACKET-004', '支架法兰', 'Q235', 'DW-B-004', '结构件', '焊接后机加'),
('PART-TURBINE-005', '涡轮叶片榫头', 'GH4169', 'DW-T-005', '航空件', '高温合金'),
('PART-SPLINE-006', '花键轴', '38CrMoAl', 'DW-S-006', '轴类件', '氮化'),
('PART-GEAR-007', '内齿圈', '42CrMo', 'DW-G-007', '齿轮件', '大模数');

INSERT OR IGNORE INTO equipment (code, name, type, model, workshop, status) VALUES
('CNC-01', '五轴加工中心-01', 'CNC', 'VT-X350', '一车间', 'ACTIVE'),
('CNC-02', '立式加工中心-02', 'CNC', 'VMC-850', '一车间', 'ACTIVE'),
('ROBOT-01', '六轴机械臂-01', 'ROBOT', 'IRB-6700', '一车间', 'ACTIVE'),
('ROBOT-02', '协作机械臂-02', 'ROBOT', 'UR-10e', '二车间', 'ACTIVE'),
('LINE-01', '滚齿自动线-01', 'LINE', 'GLS-200', '二车间', 'ACTIVE');

INSERT OR IGNORE INTO part_process (
    part_no, part_name, material, operation_no, operation_name,
    equipment_code, tool_code,
    spindle_speed, cutting_depth, feed_rate,
    speed_min, speed_max, depth_min, depth_max, feed_min, feed_max, version, approved_by, remark
) VALUES
('PART-GEAR-001', '传动齿轮', '40Cr', 10, '粗铣齿形', 'CNC-01', 'T-MILL-20', 1200, 2.5, 800, 800, 2000, 1.0, 4.0, 400, 1200, '1.0', '工艺员A', '湿切削'),
('PART-GEAR-001', '传动齿轮', '40Cr', 20, '精铣齿形', 'CNC-01', 'T-MILL-20', 1800, 0.8, 600, 1200, 2500, 0.3, 1.5, 300, 900, '1.0', '工艺员A', NULL),
('PART-GEAR-001', '传动齿轮', '40Cr', 30, '去毛刺', 'ROBOT-01', 'T-DEBUR', 3000, 0.1, 200, 2000, 4000, 0.05, 0.3, 100, 400, '1.0', '工艺员A', NULL),
('PART-GEAR-002', '从动齿轮', '20CrMnTi', 10, '滚齿粗加工', 'LINE-01', 'T-HOB-32', 220, 4.0, 1200, 150, 350, 2.0, 6.0, 800, 1500, '1.0', '工艺员B', '滚刀 Kappa'),
('PART-GEAR-002', '从动齿轮', '20CrMnTi', 20, '滚齿精加工', 'LINE-01', 'T-HOB-32', 280, 1.2, 900, 200, 400, 0.5, 2.0, 600, 1100, '1.0', '工艺员B', NULL),
('PART-SHAFT-002', '传动轴', '45钢', 10, '车外圆', 'CNC-01', 'T-TURN-12', 900, 1.2, 500, 600, 1500, 0.5, 2.5, 200, 800, '1.0', '工艺员B', NULL),
('PART-SHAFT-002', '传动轴', '45钢', 20, '铣键槽', 'CNC-02', 'T-END-10', 1100, 0.6, 350, 800, 1800, 0.2, 1.2, 150, 600, '1.0', '工艺员B', NULL),
('PART-HOUSING-003', '箱体端盖', 'HT250', 10, '粗铣平面', 'CNC-02', 'T-FACE-50', 800, 3.0, 600, 500, 1200, 1.5, 5.0, 300, 900, '1.0', '工艺员C', '铸铁切削液'),
('PART-HOUSING-003', '箱体端盖', 'HT250', 20, '精铣密封面', 'CNC-02', 'T-FACE-50', 1200, 0.4, 400, 900, 2000, 0.1, 0.8, 200, 700, '1.0', '工艺员C', 'Ra1.6'),
('PART-BRACKET-004', '支架法兰', 'Q235', 10, '钻孔攻丝', 'CNC-02', 'T-DRILL-8', 1500, NULL, 180, 1200, 2500, NULL, NULL, 100, 300, '1.0', '工艺员C', 'M8 螺纹'),
('PART-TURBINE-005', '涡轮叶片榫头', 'GH4169', 10, '五轴型面铣', 'CNC-01', 'T-BALL-6', 6500, 0.15, 280, 5000, 8000, 0.05, 0.35, 150, 400, '1.0', '工艺员D', '陶瓷刀具'),
('PART-SPLINE-006', '花键轴', '38CrMoAl', 10, '粗车', 'CNC-01', 'T-TURN-16', 750, 1.8, 450, 500, 1200, 0.8, 3.0, 200, 700, '1.0', '工艺员B', NULL),
('PART-SPLINE-006', '花键轴', '38CrMoAl', 20, '花键铣', 'CNC-01', 'T-SPLINE', 1400, 0.5, 320, 1000, 2200, 0.2, 1.0, 180, 500, '1.0', '工艺员B', NULL),
('PART-GEAR-007', '内齿圈', '42CrMo', 10, '插齿', 'LINE-01', 'T-SHAPE', 180, 2.0, 700, 120, 250, 1.0, 3.5, 400, 1000, '1.0', '工艺员A', NULL);

INSERT OR IGNORE INTO process_knowledge (category, title, content, tags, related_part_no, related_op_no, author, source, status) VALUES
('RULE', '40Cr 铣齿切深建议', '粗加工切深不超过 3mm；精加工 0.5–1.0mm；硬度 HRC>28 时进给下调 12%。', '40Cr,铣齿,切深', 'PART-GEAR-001', 10, '工艺员A', '企业标准', 'PUBLISHED'),
('RULE', '20CrMnTi 滚齿进给', '渗碳前滚齿进给不超过 1200 mm/min；精滚余量 0.8–1.2mm。', '滚齿,渗碳', 'PART-GEAR-002', 10, '工艺员B', '工艺卡片', 'PUBLISHED'),
('RULE', '高温合金切削液流量', 'GH4169 加工切削液流量不低于 18 L/min，压力 2.5 MPa。', '高温合金,冷却', 'PART-TURBINE-005', 10, '工艺员D', '材料手册', 'PUBLISHED'),
('STANDARD', 'CNC-01 主轴转速上限', '主轴转速不得超过 8000 rpm，超限须工艺员与安全员双签。', '安全,转速,CNC-01', NULL, NULL, '安全科', '设备手册', 'PUBLISHED'),
('STANDARD', '铸铁件干切禁止', 'HT250 等铸铁禁止干切，必须保证切削液覆盖刀具接触区。', '铸铁,切削液', 'PART-HOUSING-003', 10, '安全科', '环保安全', 'PUBLISHED'),
('CASE', '齿轮精铣振动偏大', '转速 2000→1800 rpm，切深 0.8→0.6 mm，Ra 由 1.8 降至 1.2。', '振动,精铣,案例', 'PART-GEAR-001', 20, '工艺员A', '2024-03 现场', 'PUBLISHED'),
('CASE', '花键铣刀崩刃', '进给 380→300 mm/min，转速维持 1400，刀具寿命提升 35%。', '崩刃,花键', 'PART-SPLINE-006', 20, '工艺员B', '2024-06 现场', 'PUBLISHED'),
('CASE', '内齿圈插齿振纹', '降低冲程速度 8%，增加专用支撑工装后振纹消除。', '插齿,振纹', 'PART-GEAR-007', 10, '工艺员A', '2025-01 现场', 'PUBLISHED'),
('FAQ', '进给与表面粗糙度', '精加工进给建议≤基准值 80%；Ra 要求高时优先降进给再降切深。', '进给,表面,FAQ', NULL, NULL, '工艺员A', 'FAQ', 'PUBLISHED'),
('FAQ', '五轴联动过切检查', '型面精加工前须做 NC 仿真与碰撞检查，首件单段空跑验证。', '五轴,仿真', 'PART-TURBINE-005', 10, '工艺员D', 'FAQ', 'PUBLISHED'),
('RULE', '机械臂去毛刺力控', 'ROBOT-01 去毛刺接触力 15–25 N，超限自动回退并报警。', '机器人,力控', 'PART-GEAR-001', 30, '工艺员A', '产线规范', 'PUBLISHED'),
('STANDARD', '优化参数采纳流程', '优化模型推荐参数须经 MES 确认或工艺员 APP 确认后方可下发 NC。', '优化,MES', NULL, NULL, '数字化部', '制度', 'PUBLISHED');

INSERT OR IGNORE INTO optimization_run (equipment_code, part_no, operation_no, pred_spindle, pred_depth, pred_feed, model_version, score, adopted, remark) VALUES
('CNC-01', 'PART-GEAR-001', 20, 1750, 0.75, 580, 'opt-v1.2', 0.92, 1, '已下发 NC'),
('CNC-01', 'PART-TURBINE-005', 10, 6200, 0.12, 265, 'opt-v1.3', 0.88, 1, '刀具磨损偏低'),
('LINE-01', 'PART-GEAR-002', 20, 265, 1.0, 850, 'opt-v1.2', 0.85, 0, '待工艺确认'),
('CNC-02', 'PART-HOUSING-003', 20, 1150, 0.35, 380, 'opt-v1.1', 0.79, 1, NULL);
