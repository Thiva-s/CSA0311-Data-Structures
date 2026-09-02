"""Web version of the Smart-City Emergency Vehicle Routing System.

The original C program is kept as the algorithm reference.  This Flask app
implements the same ideas with Python dictionaries as hash maps, heapq as the
min-heap, and an in-memory cache for repeated source/destination queries.
"""

from __future__ import annotations

import heapq
import random
import time
from dataclasses import dataclass, field
from threading import RLock
from typing import Dict, List, Optional, Tuple

from flask import Flask, jsonify, render_template, request


app = Flask(__name__)


@dataclass
class RoutingSystem:
    graph: Dict[int, Dict[int, int]] = field(default_factory=dict)
    roads: set[Tuple[int, int]] = field(default_factory=set)
    cache: Dict[Tuple[int, int], Tuple[int, List[int]]] = field(default_factory=dict)
    num_nodes: int = 0
    num_roads: int = 0
    max_weight: int = 500
    seed: Optional[int] = None
    lock: RLock = field(default_factory=RLock, repr=False)

    def generate(self, num_nodes: int = 5000, num_roads: int = 10000,
                 max_weight: int = 500, seed: Optional[int] = None) -> None:
        """Create a connected random undirected weighted road network."""
        if num_nodes < 2 or num_nodes > 6000:
            raise ValueError("Nodes must be between 2 and 6000")
        maximum_roads = num_nodes * (num_nodes - 1) // 2
        if num_roads < num_nodes - 1 or num_roads > maximum_roads:
            raise ValueError(f"Roads must be between {num_nodes - 1} and {maximum_roads}")
        if max_weight < 1 or max_weight > 100000:
            raise ValueError("Maximum travel time must be between 1 and 100000 seconds")

        rng = random.Random(seed)
        with self.lock:
            self.graph = {node: {} for node in range(num_nodes)}
            self.roads = set()
            self.cache.clear()
            self.num_nodes = num_nodes
            self.max_weight = max_weight
            self.seed = seed

            # A spanning chain guarantees that every node is reachable.
            for node in range(num_nodes - 1):
                self._add_road(node, node + 1, rng.randint(1, max_weight))

            while len(self.roads) < num_roads:
                u, v = rng.sample(range(num_nodes), 2)
                road = (min(u, v), max(u, v))
                if road not in self.roads:
                    self._add_road(u, v, rng.randint(1, max_weight))

            self.num_roads = len(self.roads)

    def _add_road(self, u: int, v: int, weight: int) -> None:
        self.graph[u][v] = weight
        self.graph[v][u] = weight
        self.roads.add((min(u, v), max(u, v)))

    def route(self, source: int, destination: int) -> dict:
        """Run Dijkstra, or return the cached result for this pair."""
        self._validate_node(source)
        self._validate_node(destination)
        key = (source, destination)
        started = time.perf_counter()
        with self.lock:
            cached = self.cache.get(key)
            if cached is not None:
                distance, path = cached
                return self._result(distance, path, True, started)

            distances = [float("inf")] * self.num_nodes
            parents = [-1] * self.num_nodes
            visited = set()
            queue: List[Tuple[int, int]] = [(0, source)]
            distances[source] = 0

            while queue:
                distance, node = heapq.heappop(queue)
                if node in visited:
                    continue
                visited.add(node)
                if node == destination:
                    break
                for neighbour, weight in self.graph[node].items():
                    if neighbour in visited:
                        continue
                    new_distance = distance + weight
                    if new_distance < distances[neighbour]:
                        distances[neighbour] = new_distance
                        parents[neighbour] = node
                        heapq.heappush(queue, (new_distance, neighbour))

            if distances[destination] == float("inf"):
                result_distance = -1
                path: List[int] = []
            else:
                result_distance = int(distances[destination])
                path = []
                current = destination
                while current != -1:
                    path.append(current)
                    current = parents[current]
                path.reverse()

            self.cache[key] = (result_distance, path)
            return self._result(result_distance, path, False, started)

    def update_traffic(self, source: int, destination: int,
                       new_weight: int, both_directions: bool = True) -> dict:
        """Change a road's travel time and invalidate affected route results."""
        self._validate_node(source)
        self._validate_node(destination)
        if new_weight < 1 or new_weight > 100000:
            raise ValueError("Travel time must be between 1 and 100000 seconds")
        with self.lock:
            if destination not in self.graph[source]:
                return {"updated": False, "cache_cleared": 0}
            self.graph[source][destination] = new_weight
            if both_directions:
                self.graph[destination][source] = new_weight
            cleared = len(self.cache)
            self.cache.clear()
            return {"updated": True, "cache_cleared": cleared}

    def stats(self) -> dict:
        with self.lock:
            return {
                "nodes": self.num_nodes,
                "roads": self.num_roads,
                "directed_edges": self.num_roads * 2,
                "cache_entries": len(self.cache),
                "max_weight": self.max_weight,
                "seed": self.seed,
            }

    def _validate_node(self, node: int) -> None:
        if node < 0 or node >= self.num_nodes:
            raise ValueError(f"Node must be between 0 and {self.num_nodes - 1}")

    @staticmethod
    def _result(distance: int, path: List[int], cached: bool, started: float) -> dict:
        return {
            "distance": distance,
            "reachable": distance >= 0,
            "path": path,
            "path_length": max(0, len(path) - 1),
            "cached": cached,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        }


system = RoutingSystem()
system.generate()


def payload() -> dict:
    data = request.get_json(silent=True) or {}
    return data


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/stats")
def get_stats():
    return jsonify(system.stats())


@app.post("/api/generate")
def generate_graph():
    data = payload()
    try:
        system.generate(
            int(data.get("nodes", 5000)),
            int(data.get("roads", 10000)),
            int(data.get("max_weight", 500)),
            int(data["seed"]) if str(data.get("seed", "")).strip() else None,
        )
        return jsonify({"stats": system.stats(), "message": "Road network generated"})
    except (TypeError, ValueError) as error:
        return jsonify({"error": str(error)}), 400


@app.post("/api/route")
def calculate_route():
    data = payload()
    try:
        result = system.route(int(data["source"]), int(data["destination"]))
        return jsonify(result)
    except (KeyError, TypeError, ValueError) as error:
        return jsonify({"error": str(error)}), 400


@app.post("/api/traffic")
def update_traffic():
    data = payload()
    try:
        result = system.update_traffic(
            int(data["source"]), int(data["destination"]), int(data["weight"])
        )
        if not result["updated"]:
            return jsonify({"error": "That road does not exist", **result}), 404
        return jsonify({"message": "Traffic updated", **result})
    except (KeyError, TypeError, ValueError) as error:
        return jsonify({"error": str(error)}), 400


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
