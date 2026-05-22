from __future__ import annotations

import math
import random
from collections import Counter
from itertools import combinations
from typing import Iterable

import numpy as np

from .config import GameConfig
from .models import HistoryItem, BombResult


Candidate = frozenset[tuple[int, int]]


class BayesianSubmarineAI:
    """観測誤差なしのベイズ更新に基づく潜水艦探索AI。

    実装上は，潜水艦配置候補を多数保持し，爆撃結果と矛盾する候補を除外する。
    残った候補から各マスの潜水艦存在確率を計算し，さらに各マスを爆撃した場合の
    結果分布のエントロピーを期待情報量として利用する。
    """

    def __init__(self, config: GameConfig, rng: random.Random | None = None) -> None:
        self.config = config
        self.rng = rng or random.Random()
        self.all_candidates: list[Candidate] = self._generate_candidates()
        self.current_candidates: list[Candidate] = list(self.all_candidates)

    def reset(self) -> None:
        self.current_candidates = list(self.all_candidates)

    def _single_submarine_placements(self) -> list[Candidate]:
        N = self.config.N
        L = self.config.L
        placements: list[Candidate] = []

        for y in range(N):
            for x in range(N - L + 1):
                cells = frozenset((x + k, y) for k in range(L))
                placements.append(cells)

        for x in range(N):
            for y in range(N - L + 1):
                cells = frozenset((x, y + k) for k in range(L))
                placements.append(cells)

        return placements

    def _generate_candidates(self) -> list[Candidate]:
        placements = self._single_submarine_placements()
        p = self.config.p
        max_candidates = self.config.max_ai_candidates

        # 組合せ総数が小さい場合は完全列挙する。
        # 大きい場合はランダムサンプリングする。
        rough_total = math.comb(len(placements), p)
        candidates: list[Candidate] = []

        if rough_total <= max_candidates * 2:
            for combo in combinations(placements, p):
                merged: set[tuple[int, int]] = set()
                valid = True
                for sub in combo:
                    if merged & sub:
                        valid = False
                        break
                    merged |= set(sub)
                if valid:
                    candidates.append(frozenset(merged))
                    if len(candidates) >= max_candidates:
                        break
        else:
            seen: set[Candidate] = set()
            attempts = 0
            max_attempts = max_candidates * 80
            while len(candidates) < max_candidates and attempts < max_attempts:
                attempts += 1
                combo = self.rng.sample(placements, p)
                merged: set[tuple[int, int]] = set()
                valid = True
                for sub in combo:
                    if merged & sub:
                        valid = False
                        break
                    merged |= set(sub)
                if not valid:
                    continue
                candidate = frozenset(merged)
                if candidate not in seen:
                    seen.add(candidate)
                    candidates.append(candidate)

        if not candidates:
            raise RuntimeError("AI候補配置を生成できませんでした。設定を確認してください。")

        return candidates

    def predict_result_for_cells(self, cells: Candidate, cell: tuple[int, int]) -> BombResult:
        x, y = cell
        min_dist = min(abs(x - sx) + abs(y - sy) for sx, sy in cells)
        if min_dist == 0:
            return "hit"
        if min_dist <= self.config.near_distance:
            return "near"
        if min_dist <= self.config.weak_distance:
            return "weak"
        return "none"

    def update_candidates(self, history: Iterable[HistoryItem]) -> None:
        history_list = list(history)
        filtered: list[Candidate] = []

        for candidate in self.all_candidates:
            ok = True
            for item in history_list:
                predicted = self.predict_result_for_cells(candidate, (item.x, item.y))
                if predicted != item.result:
                    ok = False
                    break
            if ok:
                filtered.append(candidate)

        # ランダムサンプリングの候補が偶然すべて消えた場合の保険。
        # 完全な推定ではないが，展示中に停止しないことを優先する。
        self.current_candidates = filtered if filtered else list(self.all_candidates)

    def probability_map(self, bombed_cells: set[tuple[int, int]]) -> np.ndarray:
        N = self.config.N
        prob = np.zeros((N, N), dtype=float)

        if not self.current_candidates:
            return prob

        for candidate in self.current_candidates:
            for x, y in candidate:
                prob[y, x] += 1.0

        prob /= len(self.current_candidates)

        for x, y in bombed_cells:
            prob[y, x] = 0.0

        return prob

    def information_map(self, bombed_cells: set[tuple[int, int]]) -> np.ndarray:
        N = self.config.N
        info = np.zeros((N, N), dtype=float)

        if not self.current_candidates:
            return info

        max_entropy = math.log2(4)

        for y in range(N):
            for x in range(N):
                if (x, y) in bombed_cells:
                    info[y, x] = 0.0
                    continue

                counts: Counter[str] = Counter()
                for candidate in self.current_candidates:
                    r = self.predict_result_for_cells(candidate, (x, y))
                    counts[r] += 1

                total = len(self.current_candidates)
                entropy = 0.0
                for c in counts.values():
                    p = c / total
                    if p > 0:
                        entropy -= p * math.log2(p)

                info[y, x] = entropy / max_entropy

        return info

    def score_map(self, prob: np.ndarray, info: np.ndarray, bombed_cells: set[tuple[int, int]]) -> np.ndarray:
        score = self.config.ai_alpha * prob + self.config.ai_beta * info

        for x, y in bombed_cells:
            score[y, x] = -1.0

        return score

    def compute_maps(self, history: Iterable[HistoryItem], bombed_cells: set[tuple[int, int]]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        self.update_candidates(history)
        prob = self.probability_map(bombed_cells)
        info = self.information_map(bombed_cells)
        score = self.score_map(prob, info, bombed_cells)
        return prob, info, score

    def choose_action(self, history: Iterable[HistoryItem], bombed_cells: set[tuple[int, int]]) -> tuple[int, int, np.ndarray, np.ndarray, np.ndarray, str]:
        prob, info, score = self.compute_maps(history, bombed_cells)

        max_value = np.max(score)
        ys, xs = np.where(score == max_value)
        candidates = list(zip(xs.tolist(), ys.tolist()))
        x, y = self.rng.choice(candidates)

        reason = (
            f"直撃確率 {prob[y, x]:.2f}，期待情報量 {info[y, x]:.2f}，"
            f"評価値 {score[y, x]:.2f} が高かったため"
        )

        return x, y, prob, info, score, reason
