from __future__ import annotations

import ast
import math
from pathlib import Path
from typing import Dict, List

import networkx as nx

from backend.parser import analyze_repository
from backend.graph import build_graph

FEATURES = [
    "loc", "complexity", "max_nesting", "num_args", "num_returns", "num_calls",
    "file_imports", "caller_count", "callee_count", "dependency_count", "degree",
    "betweenness", "pagerank",
]


def _source_metrics(source: str) -> Dict[str, int]:
    tree = ast.parse(source)
    decisions = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp, ast.Try, ast.ExceptHandler, ast.With, ast.AsyncWith)
    complexity = 1
    max_depth = 0

    def walk(node, depth=0):
        nonlocal complexity, max_depth
        max_depth = max(max_depth, depth)
        for child in ast.iter_child_nodes(node):
            next_depth = depth + 1 if isinstance(child, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith)) else depth
            if isinstance(child, decisions):
                complexity += 1
            if isinstance(child, ast.BoolOp):
                complexity += max(0, len(child.values) - 1)
            walk(child, next_depth)

    walk(tree)
    args = tree.body[0].args if tree.body and isinstance(tree.body[0], (ast.FunctionDef, ast.AsyncFunctionDef)) else None
    num_args = 0 if args is None else len(args.posonlyargs) + len(args.args) + len(args.kwonlyargs)
    if args is not None and args.vararg:
        num_args += 1
    if args is not None and args.kwarg:
        num_args += 1
    return {
        "loc": len(source.splitlines()),
        "complexity": complexity,
        "max_nesting": max_depth,
        "num_args": num_args,
        "num_returns": sum(isinstance(n, ast.Return) for n in ast.walk(tree)),
        "num_calls": sum(isinstance(n, ast.Call) for n in ast.walk(tree)),
    }


def analyze_with_features(repo: Path) -> List[Dict]:
    parsed = analyze_repository(str(repo))
    graph = build_graph(parsed)

    callers = {n: 0 for n in graph.nodes}
    callees = {n: 0 for n in graph.nodes}
    deps = {n: 0 for n in graph.nodes}
    for source, target, data in graph.edges(data=True):
        if data.get("type") == "CALLS":
            callers[target] = callers.get(target, 0) + 1
            callees[source] = callees.get(source, 0) + 1
        elif data.get("type") == "IMPORTS":
            deps[source] = deps.get(source, 0) + 1

    degree = dict(graph.degree())
    betweenness = nx.betweenness_centrality(graph)
    pagerank = nx.pagerank(graph) if graph.number_of_nodes() else {}
    imports = {r["file"]: len(r.get("imports", [])) for r in parsed}

    rows = []
    for record in parsed:
        file_name = record["file"]
        source_lines = Path(repo / file_name) if (repo / file_name).exists() else None
        for fn in record.get("functions", []):
            node_id = f"{file_name}:{fn['name']}"
            source = fn.get("code", "")
            metrics = _source_metrics(source)
            rows.append({
                "id": node_id,
                "file": file_name,
                "function": fn["name"],
                **metrics,
                "file_imports": imports.get(file_name, 0),
                "caller_count": callers.get(node_id, 0),
                "callee_count": callees.get(node_id, 0),
                "dependency_count": deps.get(file_name, 0),
                "degree": degree.get(node_id, 0),
                "betweenness": betweenness.get(node_id, 0.0),
                "pagerank": pagerank.get(node_id, 0.0),
            })
    return rows
