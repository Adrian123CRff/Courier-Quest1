# pathfinding.py
import heapq
from typing import List, Tuple, Optional, Dict

Cell = Tuple[int,int]

# Cache for repeated path queries
_path_cache: Dict[Tuple[Cell, Cell], Optional[List[Cell]]] = {}

def manhattan(a: Cell, b: Cell) -> int:
    return abs(a[0]-b[0]) + abs(a[1]-b[1])

def neighbors(cell: Cell):
    x,y = cell
    return [(x+1,y),(x-1,y),(x,y+1),(x,y-1)]

def reconstruct(came_from: Dict[Cell, Cell], cur: Cell) -> List[Cell]:
    path = [cur]
    while cur in came_from:
        cur = came_from[cur]
        path.append(cur)
    path.reverse()
    return path

def a_star(game_map, start: Cell, goal: Cell) -> Optional[List[Cell]]:
    """
    A* pathfinding algorithm using Manhattan distance heuristic.
    Time complexity: O(b^d) where b is branching factor, d is depth; optimal for uniform costs.
    Space complexity: O(b^d) for open/closed sets.
    Uses caching for repeated queries to improve performance.
    """
    # Check cache first
    cache_key = (start, goal)
    if cache_key in _path_cache:
        return _path_cache[cache_key]

    sx, sy = start; gx, gy = goal
    if not (0 <= sx < game_map.width and 0 <= sy < game_map.height): return None
    if not (0 <= gx < game_map.width and 0 <= gy < game_map.height): return None
    if not game_map.is_walkable(gx, gy):
        return None

    open_heap = []
    gscore = {start: 0}
    fscore = {start: manhattan(start, goal)}
    heapq.heappush(open_heap, (fscore[start], 0, start))
    came_from: Dict[Cell, Cell] = {}
    closed = set()
    counter = 1

    while open_heap:
        _, curg, current = heapq.heappop(open_heap)
        if current in closed:
            continue
        if current == goal:
            path = reconstruct(came_from, current)
            _path_cache[cache_key] = path
            return path
        closed.add(current)
        for nb in neighbors(current):
            nx, ny = nb
            if not (0 <= nx < game_map.width and 0 <= ny < game_map.height): continue
            if not game_map.is_walkable(nx, ny): continue
            tentative_g = gscore[current] + 1
            if nb not in gscore or tentative_g < gscore[nb]:
                came_from[nb] = current
                gscore[nb] = tentative_g
                f = tentative_g + manhattan(nb, goal)
                heapq.heappush(open_heap, (f, counter, nb))
                counter += 1
    _path_cache[cache_key] = None
    return None

