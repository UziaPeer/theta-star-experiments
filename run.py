"""Reproducible Theta* experiments using experiments-csv.

Nash, Daniel, Koenig, Felner (2007), https://cdn.aaai.org/AAAI/2007/AAAI07-187.pdf.
Programmer: Uzia Peer. Date: 2026-10-12.
"""

import argparse
import importlib.util
import json
import logging
import multiprocessing as mp
import os
import platform
import sys
from pathlib import Path
from random import Random
from time import perf_counter

source = os.environ.get("THETA_STAR_REPO")
if source:
    sys.path.insert(0, source)
elif importlib.util.find_spec("graphs") is None:
    local_source = Path(__file__).parents[2] / "assignment_7" / "thealgorithms-python"
    if (local_source / "graphs" / "theta_star.py").is_file():
        sys.path.insert(0, str(local_source))

# Keep plotting caches in the experiment folder, not the user's home.
os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).parent / ".mplcache"))
os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib.pyplot as plt
import networkx as nx
from experiments_csv import Experiment, plot_dataframe
from graphs.theta_star import CornerGrid, distance, path_length, theta_star


def generate_grid(size, density, seed):
    rng = Random(seed)
    cells = [
        [int(rng.random() < density / 100) for _ in range(size)] for _ in range(size)
    ]
    cells[0][0] = cells[-1][-1] = 0
    return cells


def smooth(grid, path):
    """A* PS: greedily skip consecutive visible vertices, as in the paper."""
    result, i = [path[0]], 0
    while i < len(path) - 1:
        j = i + 1
        while j + 1 < len(path) and grid.line_of_sight(path[i], path[j + 1]):
            j += 1
        result.append(path[j])
        i = j
    return result


def heading_changes(path):
    turns = 0
    for a, b, c in zip(path, path[1:], path[2:]):
        u = (b[0] - a[0], b[1] - a[1])
        v = (c[0] - b[0], c[1] - b[1])
        turns += u[0] * v[1] != u[1] * v[0] or u[0] * v[0] + u[1] * v[1] <= 0
    return turns


def grid_graph(grid):
    """Give NetworkX A* the same corner moves and costs as Theta*."""
    graph = nx.Graph()
    for y in range(grid.height + 1):
        for x in range(grid.width + 1):
            point = (x, y)
            if grid.valid_corner(point):
                graph.add_node(point)
                for neighbor in grid.neighbors(point):
                    graph.add_edge(point, neighbor, weight=distance(point, neighbor))
    return graph


def measure(size, density, seed, algorithm, optimized_file=None):
    cells = generate_grid(size, density, seed)
    module = None
    if algorithm.endswith("-cached"):
        spec = importlib.util.spec_from_file_location("cached_theta", optimized_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    t0 = perf_counter()
    grid = CornerGrid(cells)
    graph = grid_graph(grid) if algorithm in ("astar", "astar-ps") else None
    setup_seconds = perf_counter() - t0
    start, goal = (0, 0), (size, size)
    t0 = perf_counter()
    try:
        if graph is not None:
            # Octile for plain A*, Euclidean for A* PS, following the paper.
            def heuristic(a, b):
                if algorithm == "astar-ps":
                    return distance(a, b)
                dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
                return max(dx, dy) + (2**0.5 - 1) * min(dx, dy)

            path = nx.astar_path(
                graph, start, goal, heuristic=heuristic, weight="weight"
            )
            if algorithm == "astar-ps":
                path = smooth(grid, path)
        else:
            if algorithm == "basic-cached":
                path = module.theta_star_cached(cells, start, goal)
            else:
                path = theta_star(cells, start, goal)
        status = "ok"
    except nx.NetworkXNoPath:
        path, status = [], "no_path"
    seconds = perf_counter() - t0
    # Verification is outside timing, using the uncached reference geometry.
    reference = CornerGrid(cells)
    if path:
        assert path[0] == start and path[-1] == goal
        assert all(reference.line_of_sight(a, b) for a, b in zip(path, path[1:]))
    return dict(
        status=status,
        seconds=seconds,
        setup_seconds=setup_seconds,
        total_seconds=seconds + setup_seconds,
        length=path_length(path) if path else float("nan"),
        turns=heading_changes(path) if path else float("nan"),
    )


def worker(connection, parameters):
    try:
        connection.send((True, measure(**parameters)))
    except Exception as exc:
        connection.send((False, repr(exc)))
    finally:
        connection.close()


def limited_measure(limit, **parameters):
    """A separate process enforces a hard wall-time limit, including setup."""
    context = mp.get_context("spawn")
    receive, send = context.Pipe(duplex=False)
    process = context.Process(target=worker, args=(send, parameters))
    process.start()
    send.close()
    if receive.poll(limit):
        ok, result = receive.recv()
        process.join()
        receive.close()
        if not ok:
            raise RuntimeError(result)
        return result
    process.terminate()
    process.join()
    receive.close()
    return dict(
        status="timeout",
        seconds=float("nan"),
        setup_seconds=float("nan"),
        total_seconds=float("nan"),
        length=float("nan"),
        turns=float("nan"),
        expansions=float("nan"),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="+", default=[10, 20, 40, 80])
    parser.add_argument("--densities", type=int, nargs="+", default=[0, 10, 20, 30])
    parser.add_argument("--seeds", type=int, default=10)
    parser.add_argument(
        "--algorithms", nargs="+", default=["astar", "astar-ps", "basic"]
    )
    parser.add_argument("--limit", type=float, default=60)
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).parent / "results"
    )
    parser.add_argument("--optimized-file", type=str)
    parser.add_argument(
        "--direct", action="store_true", help="For small tests only; no hard timeout"
    )
    args = parser.parse_args()
    if any(
        a not in ("astar", "astar-ps", "basic", "basic-cached") for a in args.algorithms
    ):
        parser.error("Unknown algorithm")
    if any(a.endswith("-cached") for a in args.algorithms) and not args.optimized_file:
        parser.error("Cached algorithms require --optimized-file")
    args.output.mkdir(parents=True, exist_ok=True)
    logging.getLogger("experiments_csv.Experiment").setLevel(logging.WARNING)
    experiment = Experiment(str(args.output), "runs.csv", backup_folder=None)

    def single(size, density, seed, algorithm):
        params = dict(
            size=size,
            density=density,
            seed=seed,
            algorithm=algorithm,
            optimized_file=args.optimized_file,
        )
        result = (
            measure(**params) if args.direct else limited_measure(args.limit, **params)
        )
        print(
            size,
            density,
            seed,
            algorithm,
            result["status"],
            round(result["seconds"], 4),
            flush=True,
        )
        return result

    experiment.run(
        single,
        dict(
            size=sorted(args.sizes),
            density=args.densities,
            seed=list(range(args.seeds)),
            algorithm=args.algorithms,
        ),
    )
    data = experiment.dataFrame
    for metric in ("seconds", "total_seconds", "length", "turns"):
        fig, axes = plt.subplots(
            1, len(args.densities), figsize=(5 * len(args.densities), 4), squeeze=False
        )
        for ax, density in zip(axes[0], args.densities):
            subset = data[(data.density == density) & (data.status == "ok")].copy()
            if not subset.empty:
                plot_dataframe(ax, subset, "size", metric, "algorithm")
                ax.legend(fontsize=8)
            ax.set(
                title=f"Blocked cells: {density}%",
                xlabel="Grid side (cells)",
                ylabel=metric,
            )
            ax.grid(alpha=0.2)
        fig.tight_layout()
        fig.savefig(args.output / f"{metric}.png", dpi=130)
        plt.close(fig)
    metadata = dict(
        python=platform.python_version(),
        platform=platform.platform(),
        processor=platform.processor(),
        arguments=vars(args),
        timing="seconds excludes grid/graph setup; total_seconds includes it; validation excluded",
        tie_breaking="Theta*: smaller g; NetworkX A*: insertion order (not identical to paper)",
    )
    (args.output / "metadata.json").write_text(
        json.dumps(metadata, indent=2, default=str), encoding="utf-8"
    )
    successful_times = data.copy()
    for column in ("seconds", "total_seconds"):
        successful_times[column] = successful_times[column].where(data.status == "ok")
    summary = successful_times.groupby(["size", "density", "algorithm"]).agg(
        runs=("status", "size"),
        successes=("status", lambda s: sum(s == "ok")),
        mean_seconds=("seconds", "mean"),
        median_seconds=("seconds", "median"),
        mean_total_seconds=("total_seconds", "mean"),
        mean_length=("length", "mean"),
        mean_turns=("turns", "mean"),
    )
    summary.to_csv(args.output / "summary.csv")


if __name__ == "__main__":
    main()
