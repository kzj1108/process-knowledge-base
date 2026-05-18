"""向知识库 API 推送模拟实时数据（联调 Unity 用）"""
import json
import math
import time
import urllib.request

API = "http://127.0.0.1:8090/api/v1/machining/realtime"
EQUIPMENT = "CNC-01"


def post(payload: dict) -> None:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        print(resp.read().decode())


def main() -> None:
    t0 = time.time()
    print(f"POST -> {API}")
    while True:
        t = time.time() - t0
        post(
            {
                "equipment_code": EQUIPMENT,
                "part_no": "PART-GEAR-001",
                "spindle_speed": 1200 + 50 * math.sin(t),
                "cutting_depth": 2.0,
                "feed_rate": 800,
                "axis_x": 120 * math.sin(t),
                "axis_y": 80 * math.cos(t * 0.7),
                "axis_z": 40 * math.sin(t * 0.4),
                "joint_angles": [10 * math.sin(t + i) for i in range(6)],
                "status": "RUN",
            }
        )
        time.sleep(0.1)


if __name__ == "__main__":
    main()
