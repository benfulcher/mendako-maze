#!/usr/bin/env python3
"""maze_gen.py: square-grid mazes with two-way, one-way and hard edges.

Model
-----
Each cell of an n x n grid is a node of a directed graph.
Each pair of side-by-side cells is joined by one edge of three kinds:

    wall     hard edge: no passage either way
    open     two-way passage        (a ladder: climb up or down)
    one-way  passage u -> v only    (a hole in the floor: drop, no way back)

"Solvable" means the goal is reachable from the start following the edge
directions.

Generation
----------
1. Carve a spanning tree (recursive backtracker) of two-way passages.
   This is a perfect maze: exactly one route between any two cells.
2. Knock down `--loops` extra walls so the maze has cycles.
   One-way edges only matter when there are alternative routes.
3. Turn a fraction `--oneway` of the passages into one-way edges, one at a
   time in random order, keeping each only if the maze stays valid:
     always     goal reachable from start
     --fair     no traps: every cell you can reach can still reach the goal
     --keep-all every cell stays reachable from the start
     --gravity  the one-way edges form a DAG, so every cell gets a floor
                number and every one-way edge drops to a lower floor
                (the platform / ladder / hole picture)
     --platform rows are floors seen from the side: horizontal edges are
                walls or open, vertical two-way edges are ladders (H) and
                the only one-way edges are holes (o) that drop you one floor

Usage
-----
    python3 maze_gen.py -n 12 --seed 1 --solution
    python3 maze_gen.py -n 20 --oneway 0.4 --fair --svg maze.svg --json maze.json
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import deque

WALL = "wall"
OPEN = "open"


def ekey(a, b):
    """Canonical key for the undirected edge {a, b}."""
    return (a, b) if a < b else (b, a)


class Maze:
    def __init__(self, rows, cols, start, goal):
        self.rows = rows
        self.cols = cols
        self.start = start
        self.goal = goal
        # Edge state: WALL, OPEN, or a tuple (u, v) meaning one-way u -> v.
        self.edges = {}
        for r in range(rows):
            for c in range(cols):
                if c + 1 < cols:
                    self.edges[ekey((r, c), (r, c + 1))] = WALL
                if r + 1 < rows:
                    self.edges[ekey((r, c), (r + 1, c))] = WALL

    # ---- graph queries ---------------------------------------------------
    def cells(self):
        return [(r, c) for r in range(self.rows) for c in range(self.cols)]

    def neighbours(self, cell):
        r, c = cell
        for dr, dc in ((-1, 0), (0, 1), (1, 0), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < self.rows and 0 <= nc < self.cols:
                yield (nr, nc)

    def passable(self, u, v, oneway_only=False):
        st = self.edges[ekey(u, v)]
        if st == WALL:
            return False
        if st == OPEN:
            return not oneway_only
        return st == (u, v)

    def successors(self, u, oneway_only=False):
        return [v for v in self.neighbours(u) if self.passable(u, v, oneway_only)]

    def predecessors(self, u, oneway_only=False):
        return [v for v in self.neighbours(u) if self.passable(v, u, oneway_only)]

    def bfs(self, src, step):
        """Map cell -> parent for every cell reachable from src via step()."""
        parent = {src: None}
        q = deque([src])
        while q:
            u = q.popleft()
            for v in step(u):
                if v not in parent:
                    parent[v] = u
                    q.append(v)
        return parent

    def reachable_from_start(self):
        return set(self.bfs(self.start, self.successors))

    def can_reach_goal(self):
        return set(self.bfs(self.goal, self.predecessors))

    def solution(self):
        """Shortest directed path start -> goal, or None."""
        parent = self.bfs(self.start, self.successors)
        if self.goal not in parent:
            return None
        path = [self.goal]
        while path[-1] != self.start:
            path.append(parent[path[-1]])
        return path[::-1]

    def oneway_floors(self):
        """Floor number per cell if the one-way edges are acyclic, else None.

        Every one-way edge u -> v then has floor[u] > floor[v]: a hole drops
        you to a lower floor.  Cells touching no one-way edge sit on floor 0.
        """
        indeg = {c: len(self.predecessors(c, True)) for c in self.cells()}
        order = []
        q = deque(c for c in self.cells() if indeg[c] == 0)
        while q:
            u = q.popleft()
            order.append(u)
            for v in self.successors(u, True):
                indeg[v] -= 1
                if indeg[v] == 0:
                    q.append(v)
        if len(order) != len(self.cells()):
            return None  # a directed cycle made only of one-way edges
        floors = {c: 0 for c in self.cells()}
        for u in reversed(order):
            for v in self.successors(u, True):
                floors[u] = max(floors[u], floors[v] + 1)
        return floors

    def is_valid(self, fair=False, gravity=False, keep_all=False):
        reach = self.reachable_from_start()
        if self.goal not in reach:
            return False
        if keep_all and len(reach) != len(self.cells()):
            return False
        if fair and not reach <= self.can_reach_goal():
            return False
        if gravity and self.oneway_floors() is None:
            return False
        return True


# ---- generation ----------------------------------------------------------
def carve_tree(maze, rng):
    """Recursive backtracker: a random spanning tree of two-way passages."""
    start = (rng.randrange(maze.rows), rng.randrange(maze.cols))
    visited = {start}
    stack = [start]
    while stack:
        u = stack[-1]
        fresh = [v for v in maze.neighbours(u) if v not in visited]
        if not fresh:
            stack.pop()
            continue
        v = rng.choice(fresh)
        maze.edges[ekey(u, v)] = OPEN
        visited.add(v)
        stack.append(v)


def add_loops(maze, rng, k):
    """Remove k random internal walls, creating k cycles."""
    walls = [e for e, s in maze.edges.items() if s == WALL]
    rng.shuffle(walls)
    for e in walls[:k]:
        maze.edges[e] = OPEN


def orient_edges(maze, rng, fraction, fair, gravity, keep_all, platform=False):
    """Make about `fraction` of the passages one-way, keeping the maze valid.

    Each passage is tried in a random direction, then the other; if neither
    keeps the maze valid it stays two-way.  In platform mode only vertical
    passages are tried, and only downward (holes).  Returns the number converted.
    """
    passages = [e for e, s in maze.edges.items() if s == OPEN
                and not (platform and e[0][0] == e[1][0])]
    rng.shuffle(passages)
    target = round(fraction * len(passages))
    made = 0
    for e in passages:
        if made >= target:
            break
        a, b = e  # a is above b (or left of b)
        for direction in ([(a, b)] if platform else rng.sample([(a, b), (b, a)], 2)):
            maze.edges[e] = direction
            if maze.is_valid(fair, gravity, keep_all):
                made += 1
                break
        else:  # neither direction worked
            maze.edges[e] = OPEN
    return made, target


def generate(n, seed=None, oneway=0.25, loops=None, fair=False, gravity=False,
             keep_all=False, start=None, goal=None, rows=None, platform=False):
    """Build a maze; returns (maze, one-way edges made, one-way edges targeted)."""
    rng = random.Random(seed)
    rows = rows or n
    start = start or (0, 0)
    goal = goal or (rows - 1, n - 1)
    maze = Maze(rows, n, start, goal)
    carve_tree(maze, rng)
    add_loops(maze, rng, max(rows, n) if loops is None else loops)
    made, target = orient_edges(maze, rng, oneway, fair, gravity, keep_all, platform)
    assert maze.solution() is not None, "generator produced an unsolvable maze"
    return maze, made, target


# ---- rendering -----------------------------------------------------------
def render_ascii(maze, path=None, platform=False):
    """Cells are 3 chars wide and 1 high; arrows mark one-way passages.

    In platform mode a two-way vertical passage is a ladder (H) and a
    one-way one is a hole (o); floors are numbered from the bottom.
    """
    H, W = 2 * maze.rows + 1, 4 * maze.cols + 1
    g = [[" "] * W for _ in range(H)]
    for i in range(H):
        for j in range(W):
            if i % 2 == 0:
                g[i][j] = "+" if j % 4 == 0 else "-"
            elif j % 4 == 0:
                g[i][j] = "|"
    for (a, b), st in maze.edges.items():
        if st == WALL:
            continue
        (r1, c1), (r2, c2) = a, b
        if r1 == r2:  # boundary between two cells in the same row
            i, j = 2 * r1 + 1, 4 * max(c1, c2)
            if st == OPEN:
                g[i][j] = " "
            else:
                g[i][j] = ">" if st[1][1] > st[0][1] else "<"
        else:  # boundary between two cells in the same column
            i, j = 2 * max(r1, r2), 4 * c1 + 1
            if st == OPEN:
                mark = " H " if platform else "   "
            elif platform:
                mark = " o "
            else:
                mark = " v " if st[1][0] > st[0][0] else " ^ "
            g[i][j:j + 3] = list(mark)
    if path:
        for r, c in path:
            g[2 * r + 1][4 * c + 2] = "."
    sr, sc = maze.start
    gr, gc = maze.goal
    g[2 * sr + 1][4 * sc + 2] = "S"
    g[2 * gr + 1][4 * gc + 2] = "G"
    lines = ["".join(row) for row in g]
    if platform:
        lines = [(f"{maze.rows - i // 2:2d} " if i % 2 else "   ") + ln for i, ln in enumerate(lines)]
    return "\n".join(lines)


def render_svg(maze, path=None, cell=28, margin=12):
    width, height = 2 * margin + maze.cols * cell, 2 * margin + maze.rows * cell
    X = lambda c: margin + c * cell  # noqa: E731
    Y = lambda r: margin + r * cell  # noqa: E731
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="white"/>',
    ]
    if path:
        pts = " ".join(f"{X(c) + cell / 2:.1f},{Y(r) + cell / 2:.1f}" for r, c in path)
        out.append(f'<polyline points="{pts}" fill="none" stroke="#f5b041" '
                   f'stroke-width="{cell / 5:.1f}" stroke-linejoin="round" '
                   f'stroke-linecap="round" opacity="0.7"/>')
    for (r, c), colour, label in ((maze.start, "#2e86c1", "S"), (maze.goal, "#28b463", "G")):
        cx, cy = X(c) + cell / 2, Y(r) + cell / 2
        out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{cell * 0.3:.1f}" fill="{colour}"/>')
        out.append(f'<text x="{cx:.1f}" y="{cy:.1f}" font-size="{cell * 0.4:.1f}" '
                   f'font-family="sans-serif" fill="white" text-anchor="middle" '
                   f'dominant-baseline="central">{label}</text>')
    walls = []
    arrows = []
    s = cell * 0.32  # arrowhead size
    for (a, b), st in maze.edges.items():
        (r1, c1), (r2, c2) = a, b
        if r1 == r2:  # vertical boundary
            x, y0 = X(max(c1, c2)), Y(r1)
            if st == WALL:
                walls.append(f"M{x} {y0}v{cell}")
            elif st != OPEN:
                cy = y0 + cell / 2
                d = 1 if st[1][1] > st[0][1] else -1
                arrows.append(f"{x - d * s / 2:.1f},{cy - s / 2:.1f} "
                              f"{x - d * s / 2:.1f},{cy + s / 2:.1f} "
                              f"{x + d * s / 2:.1f},{cy:.1f}")
        else:  # horizontal boundary
            x0, y = X(c1), Y(max(r1, r2))
            if st == WALL:
                walls.append(f"M{x0} {y}h{cell}")
            elif st != OPEN:
                cx = x0 + cell / 2
                d = 1 if st[1][0] > st[0][0] else -1
                arrows.append(f"{cx - s / 2:.1f},{y - d * s / 2:.1f} "
                              f"{cx + s / 2:.1f},{y - d * s / 2:.1f} "
                              f"{cx:.1f},{y + d * s / 2:.1f}")
    out.append(f'<path d="{" ".join(walls)}" stroke="black" stroke-width="2" '
               f'stroke-linecap="square" fill="none"/>')
    out.append(f'<rect x="{X(0)}" y="{Y(0)}" width="{maze.cols * cell}" height="{maze.rows * cell}" '
               f'fill="none" stroke="black" stroke-width="3"/>')
    for pts in arrows:
        out.append(f'<polygon points="{pts}" fill="#c0392b"/>')
    out.append("</svg>")
    return "\n".join(out)


def to_dict(maze, path=None, floors=None):
    edges = []
    for (a, b), st in sorted(maze.edges.items()):
        if st == WALL:
            edges.append({"cells": [a, b], "type": "wall"})
        elif st == OPEN:
            edges.append({"cells": [a, b], "type": "open"})
        else:
            edges.append({"cells": [a, b], "type": "oneway", "from": st[0], "to": st[1]})
    d = {"rows": maze.rows, "cols": maze.cols, "start": maze.start, "goal": maze.goal,
         "edges": edges, "solution": path}
    if floors is not None:
        d["floors"] = [[floors[(r, c)] for c in range(maze.cols)] for r in range(maze.rows)]
    return d


# ---- CLI -----------------------------------------------------------------
def parse_cell(text):
    r, c = (int(x) for x in text.split(","))
    return (r, c)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-n", "--size", type=int, default=10, help="columns (and rows unless --rows) (default 10)")
    p.add_argument("--rows", type=int, help="rows, or floors with --platform (default: same as --size)")
    p.add_argument("--platform", action="store_true",
                   help="side view: floors joined by ladders (two-way) and holes (down only)")
    p.add_argument("--seed", type=int, help="random seed for a reproducible maze")
    p.add_argument("--oneway", type=float, default=0.25,
                   help="target fraction of passages made one-way (default 0.25)")
    p.add_argument("--loops", type=int,
                   help="extra walls to remove, creating cycles (default: size)")
    p.add_argument("--fair", action="store_true",
                   help="no traps: every reachable cell can still reach the goal")
    p.add_argument("--keep-all", action="store_true",
                   help="every cell stays reachable from the start")
    p.add_argument("--gravity", action="store_true",
                   help="one-way edges are acyclic, so cells get floor numbers "
                        "and every one-way edge drops a floor")
    p.add_argument("--start", type=parse_cell, metavar="R,C", help="start cell (default 0,0)")
    p.add_argument("--goal", type=parse_cell, metavar="R,C", help="goal cell (default n-1,n-1)")
    p.add_argument("--solution", action="store_true", help="mark the shortest solution")
    p.add_argument("--svg", metavar="FILE", help="write an SVG drawing")
    p.add_argument("--json", metavar="FILE", help="write the maze graph as JSON")
    p.add_argument("--quiet", action="store_true", help="don't print the ASCII maze")
    args = p.parse_args(argv)

    maze, made, target = generate(
        args.size, seed=args.seed, oneway=args.oneway, loops=args.loops,
        fair=args.fair, gravity=args.gravity, keep_all=args.keep_all,
        start=args.start, goal=args.goal, rows=args.rows, platform=args.platform)
    path = maze.solution()
    floors = maze.oneway_floors() if args.gravity else None

    if not args.quiet:
        print(render_ascii(maze, path if args.solution else None, args.platform))

    n_pass = sum(1 for s in maze.edges.values() if s != WALL)
    n_one = sum(1 for s in maze.edges.values() if s not in (WALL, OPEN))
    on_path = sum(1 for u, v in zip(path, path[1:]) if maze.edges[ekey(u, v)] == (u, v))
    reach = maze.reachable_from_start()
    traps = reach - maze.can_reach_goal()
    print(f"size {maze.rows}x{maze.cols}, seed {args.seed}", file=sys.stderr)
    short = f" (constraints allowed only {made} of the {target} targeted)" if made < target else ""
    print(f"passages {n_pass}, one-way {n_one} ({n_one / n_pass:.0%}){short}, "
          f"walls {len(maze.edges) - n_pass}", file=sys.stderr)
    print(f"solution length {len(path) - 1} steps, {on_path} one-way steps", file=sys.stderr)
    print(f"cells: {len(reach)} reachable, {len(traps)} trapped (no way to goal), "
          f"{len(maze.cells()) - len(reach)} unreachable", file=sys.stderr)
    if floors is not None:
        print(f"floors: {max(floors.values()) + 1} (start on floor {floors[maze.start]}, "
              f"goal on floor {floors[maze.goal]})", file=sys.stderr)

    if args.svg:
        with open(args.svg, "w") as f:
            f.write(render_svg(maze, path if args.solution else None))
        print(f"wrote {args.svg}", file=sys.stderr)
    if args.json:
        with open(args.json, "w") as f:
            json.dump(to_dict(maze, path, floors), f, indent=1)
        print(f"wrote {args.json}", file=sys.stderr)


if __name__ == "__main__":
    main()
