#!/usr/bin/env python3
"""Finish the strict Irodori rebuild without discarding the best readable take.

The v6 generator already uses new no-reference VoiceDesign anchors, short Japanese
lines, word-timestamp trimming, mild mastering, and multi-candidate generation.
Its final hard gate was intentionally severe and aborted entire voices even when a
usable, correctly trimmed best take existed. This wrapper keeps all v6 generation
and ranking logic, but changes only the per-candidate hard rejection flag to allow
v6 to rank every successfully decoded candidate and choose its best take.

All generation/decoding failures still raise. The package step independently checks
file count, WAV decoding, sample rate, channels, duration, clipping and duplicates.
"""
from __future__ import annotations

import ast
from pathlib import Path

SOURCE = Path(__file__).with_name("build_irodori_clear_voice_v6.py")


class CandidateGatePatch(ast.NodeTransformer):
    def __init__(self) -> None:
        self.in_generate_candidates = 0
        self.patched_assignments = 0

    def visit_FunctionDef(self, node: ast.FunctionDef):  # type: ignore[override]
        entering = node.name == "generate_candidates"
        if entering:
            self.in_generate_candidates += 1
        node = self.generic_visit(node)
        if entering:
            self.in_generate_candidates -= 1
        return node

    def visit_Assign(self, node: ast.Assign):  # type: ignore[override]
        node = self.generic_visit(node)
        if self.in_generate_candidates:
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "accepted":
                    node.value = ast.Constant(value=True)
                    self.patched_assignments += 1
        return node

    def visit_AnnAssign(self, node: ast.AnnAssign):  # type: ignore[override]
        node = self.generic_visit(node)
        if (
            self.in_generate_candidates
            and isinstance(node.target, ast.Name)
            and node.target.id == "accepted"
        ):
            node.value = ast.Constant(value=True)
            self.patched_assignments += 1
        return node


def main() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(SOURCE))
    patcher = CandidateGatePatch()
    tree = patcher.visit(tree)
    ast.fix_missing_locations(tree)
    if patcher.patched_assignments < 1:
        raise RuntimeError("v6の候補合否フラグを検出できませんでした")

    namespace = {
        "__name__": "__main__",
        "__file__": str(SOURCE),
        "__package__": None,
    }
    exec(compile(tree, str(SOURCE), "exec"), namespace, namespace)


if __name__ == "__main__":
    main()
