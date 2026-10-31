# メンダコの めいろ (Mendako Maze)

A deep-sea maze game for the iPad, where a メンダコ (flapjack octopus) hunts for a pearl in the dark.
It lives at https://benfulcher.github.io/mendako-maze/ and is deployed from `web/` by `.github/workflows/pages.yml` on every push to `main`.
Open it in Safari on the iPad and choose Share → Add to Home Screen.

## The maze

The maze is a directed graph on a square grid.
Each pair of side-by-side cells is joined by a wall (rock), a two-way passage, or a one-way passage drawn as a current of chevrons you can only swim along with.
Topologically this is the same as a stack of platforms joined by ladders (two-way) and holes in the floor (one-way down), except that a general grid maze also allows one-way loops.

The game draws each maze in one of two ways; the みかた ⇄ button at the top left switches to the other view with a fresh maze:

- **よこから** (from the side): rows are floors, up to eight of them, seen side-on.
  Rock pillars block the way along a floor, ladders join floors both ways, and black oval holes in the floor drop her one floor down with no way back up.
  She starts at the bottom left and climbs the tower to the pearl.
- **うえから** (from above): a square grid seen from above, where one-way passages are currents of chevrons she can only swim along with.

The view is zoomed in, with the camera following the octopus (from the side a whole floor's width is always shown, and the camera scrolls up the tower); when the maze doesn't fit on the screen a 🗺️ button toggles a view of the whole maze.

Each level is generated fresh:

1. A spanning tree of two-way passages (recursive backtracker), so every cell is connected.
2. Some extra walls are removed to make loops.
3. Passages are turned one-way one at a time, in random order, and each change is kept only if the goal is still reachable from the start.
   By default the maze is also *fair*: every cell you can reach can still reach the goal, so a wrong turn costs time but never the game.
4. The pearl goes at the cell with the longest shortest path from the start, so it is as far away as the maze allows.
   From the side it stays in the top half of the tower: often the top floor, but sometimes a spot you have to climb past and drop down onto.

Levels get bigger (5×5 up to 12×12 from above; 4 to 8 floors and 10 to 14 tiles wide from the side) and gain more one-way passages.

## Playing

- Move with the on-screen arrows (hold to keep going), a swipe on the maze, or the arrow keys.
- Swimming into a current the wrong way pushes you back; a hole can't be climbed.
- 💡 lights up the next few steps of the shortest way to the pearl.
- ⚙️ settings:
  - **くらさ** (darkness): あかるい shows the whole maze; ランタン (default) shows what's near the octopus and dimly remembers where she has been; まっくら shows only what's near and remembers nothing.
  - **いきどまり の わな** (dead-end traps): off by default. On, some regions can be entered but not left; a 🌀 whirlpool button then takes her back to the start.
  - **みかた** (view): よこから (default) or うえから.
  - **レベル** to jump between levels, and あたらしい めいろ for a fresh maze at the same level.

Progress (level, pearls found, settings) is saved in the browser on that device.

## Python generator

`maze_gen.py` is a standalone generator of the same mazes, useful for printing:

```
python3 maze_gen.py -n 12 --seed 1 --solution            # ASCII maze with the solution marked
python3 maze_gen.py -n 20 --fair --keep-all --svg maze.svg --json maze.json
python3 maze_gen.py -n 10 --gravity                       # one-way edges never form a cycle (every cell gets a floor number)
python3 maze_gen.py -n 12 --rows 8 --platform --fair --far-goal   # side view: 8 floors, ladders (H) and holes (o)
```
