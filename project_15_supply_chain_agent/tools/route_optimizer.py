# tools/route_optimizer.py — 配送路径优化工具（最近邻启发式算法）
from __future__ import annotations

import math
from dataclasses import dataclass, field

from config import MAX_ROUTE_STOPS, SPEED_KMH


@dataclass
class DeliveryStop:
    """配送站点。"""
    stop_id: str
    name: str
    lat: float
    lon: float
    demand: float = 0.0       # 配送量（件）
    time_window: tuple[int, int] = (8, 18)  # 可配送时间窗口（小时）

    def distance_to(self, other: "DeliveryStop") -> float:
        """计算两站点之间的直线距离（km，Haversine 近似）。"""
        R = 6371
        lat1, lon1 = math.radians(self.lat), math.radians(self.lon)
        lat2, lon2 = math.radians(other.lat), math.radians(other.lon)
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        return R * 2 * math.asin(math.sqrt(a))


@dataclass
class RouteResult:
    """路径优化结果。"""
    route: list[str]          # 站点 ID 顺序
    total_distance_km: float
    estimated_hours: float
    stops_count: int
    efficiency_score: float   # 每公里配送点数

    def to_dict(self) -> dict:
        return {
            "配送顺序": self.route,
            "总距离(km)": round(self.total_distance_km, 2),
            "预计耗时(h)": round(self.estimated_hours, 2),
            "站点数": self.stops_count,
            "效率得分": round(self.efficiency_score, 3),
        }


def optimize_route(depot: DeliveryStop, stops: list[DeliveryStop]) -> RouteResult:
    """
    最近邻启发式算法优化配送路径（从仓库出发，访问所有站点后返回）。

    Args:
        depot: 仓库起点
        stops: 待配送站点列表

    Returns:
        RouteResult
    """
    if not stops:
        return RouteResult(
            route=[depot.stop_id],
            total_distance_km=0,
            estimated_hours=0,
            stops_count=0,
            efficiency_score=0,
        )

    # 限制最大站点数
    stops = stops[:MAX_ROUTE_STOPS]

    unvisited = list(stops)
    route_ids = [depot.stop_id]
    route_stops = [depot]
    total_dist = 0.0

    current = depot
    while unvisited:
        nearest = min(unvisited, key=lambda s: current.distance_to(s))
        dist = current.distance_to(nearest)
        total_dist += dist
        route_ids.append(nearest.stop_id)
        route_stops.append(nearest)
        unvisited.remove(nearest)
        current = nearest

    # 返回仓库
    total_dist += current.distance_to(depot)
    route_ids.append(depot.stop_id)

    estimated_hours = total_dist / SPEED_KMH
    efficiency = len(stops) / total_dist if total_dist > 0 else 0

    return RouteResult(
        route=route_ids,
        total_distance_km=total_dist,
        estimated_hours=estimated_hours,
        stops_count=len(stops),
        efficiency_score=efficiency,
    )


def detect_delay_risk(stops: list[DeliveryStop], route_result: RouteResult,
                      start_hour: int = 8) -> list[dict]:
    """
    根据路径和时间窗口检测潜在延误风险。
    """
    risks = []
    current_hour = float(start_hour)
    stop_map = {s.stop_id: s for s in stops}

    for i in range(1, len(route_result.route) - 1):  # 跳过仓库
        sid = route_result.route[i]
        stop = stop_map.get(sid)
        if stop is None:
            continue
        # 累计行驶时间（简化：平均分配）
        current_hour += route_result.estimated_hours / max(route_result.stops_count, 1)
        arrival_hour = current_hour

        window_end = stop.time_window[1]
        if arrival_hour > window_end:
            risks.append({
                "stop_id": sid,
                "stop_name": stop.name,
                "estimated_arrival": f"{int(arrival_hour):02d}:{int((arrival_hour % 1)*60):02d}",
                "time_window_end": f"{window_end:02d}:00",
                "risk": "超出配送时间窗口",
            })

    return risks
