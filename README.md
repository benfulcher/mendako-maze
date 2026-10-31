# メンダコの めいろ (Mendako Maze)

A deep-sea maze game for the iPad, where a メンダコ (flapjack octopus) hunts for a pearl in the dark.
It lives at https://benfulcher.github.io/mendako-maze/ and is deployed from `web/` by `.github/workflows/pages.yml` on every push to `main`.
Open it in Safari on the iPad and choose Share → Add to Home Screen.

## The maze

The maze is a directed graph on a square grid.
Each pair of side-by-side cells is joined by a wall (rock), a two-way passage, or a one-way passage drawn as a current of chevrons you can only swim along with.
Topologically this is the same as a stack of platforms joined by ladders (two-way) and holes in the floor (one-way down), except that a general grid maze also allows one-way loops; the Python generator's `--gravity` option restricts it to the platform picture.

Each level is generated fresh:

1. A spanning tree of two-way passages (recursive backtracker), so every cell is connected.
2. Some extra walls are removed to make loops.
3. Passages are turned one-way one at a time, in random order, and each change is kept only if the goal is still reachable from the start.
   By default the maze is also *fair*: every cell you can reach can still reach the goal, so a wrong turn costs time but never the game.

Levels get bigger (5×5 up to 12×12) and gain more one-way currents.

## Playing

- Move with the on-screen arrows (hold to keep going), a swipe on the maze, or the arrow keys.
- Swimming into a current the wrong way pushes you back.
- 💡 lights up the next few steps of the shortest way to the pearl.
- ⚙️ settings:
  - **くらさ** (darkness): あかるい shows the whole maze; ランタン (default) shows what's near the octopus and dimly remembers where she has been; まっくら shows only what's near and remembers nothing.
  - **いきどまり の わな** (dead-end traps): off by default. On, some regions can be entered but not left; a 🌀 whirlpool button then takes her back to the start.
  - **レベル** to jump between levels, and あたらしい めいろ for a fresh maze at the same level.

Progress (level, pearls found, settings) is saved in the browser on that device.

## Python generator

`maze_gen.py` is a standalone generator of the same mazes, useful for printing:

```
python3 maze_gen.py -n 12 --seed 1 --solution            # ASCII maze with the solution marked
python3 maze_gen.py -n 20 --fair --keep-all --svg maze.svg --json maze.json
python3 maze_gen.py -n 10 --gravity                       # platform/ladder/hole model: one-way edges never form a cycle
```
