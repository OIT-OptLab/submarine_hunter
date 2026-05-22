from __future__ import annotations

import random

import numpy as np

from .ai import BayesianSubmarineAI
from .config import GameConfig
from .models import Submarine, HistoryItem, Actor, BombResult


class SubmarineHunterGame:
    def __init__(self, config: GameConfig, seed: int | None = None) -> None:
        self.config = config
        self.rng = random.Random(seed)

        self.submarines: list[Submarine] = []
        self.history: list[HistoryItem] = []
        self.bombed_cells: set[tuple[int, int]] = set()

        self.turn = 1
        self.action_index = 1
        self.score_human = 0
        self.score_ai = 0
        self.game_over = False
        self.last_message = ""

        self.awaiting_human_bonus = False
        self.ai = BayesianSubmarineAI(config, self.rng)

        self._place_submarines()

    def _place_submarines(self) -> None:
        N = self.config.N
        L = self.config.L
        occupied: set[tuple[int, int]] = set()

        for sid in range(self.config.p):
            for _ in range(5000):
                orientation = self.rng.choice(["horizontal", "vertical"])

                if orientation == "horizontal":
                    x = self.rng.randint(0, N - L)
                    y = self.rng.randint(0, N - 1)
                    cells = [(x + k, y) for k in range(L)]
                else:
                    x = self.rng.randint(0, N - 1)
                    y = self.rng.randint(0, N - L)
                    cells = [(x, y + k) for k in range(L)]

                if not (set(cells) & occupied):
                    self.submarines.append(Submarine(id=sid, cells=cells))
                    occupied |= set(cells)
                    break
            else:
                raise RuntimeError("潜水艦の配置に失敗しました。")

    def all_submarine_cells(self) -> set[tuple[int, int]]:
        cells: set[tuple[int, int]] = set()
        for sub in self.submarines:
            cells |= set(sub.cells)
        return cells

    def min_distance_to_submarine(self, cell: tuple[int, int]) -> int:
        x, y = cell
        return min(abs(x - sx) + abs(y - sy) for sx, sy in self.all_submarine_cells())

    def judge_bomb(self, cell: tuple[int, int]) -> BombResult:
        d = self.min_distance_to_submarine(cell)

        if d == 0:
            return "hit"
        if d <= self.config.near_distance:
            return "near"
        if d <= self.config.weak_distance:
            return "weak"
        return "none"

    def get_submarine_at(self, cell: tuple[int, int]) -> Submarine | None:
        for sub in self.submarines:
            if sub.contains(cell):
                return sub
        return None

    def is_finished(self) -> bool:
        if all(sub.sunk for sub in self.submarines):
            return True
        if self.turn > self.config.max_turns:
            return True
        return False

    def bomb(
        self,
        actor: Actor,
        cell: tuple[int, int],
        is_bonus_action: bool = False,
        ai_maps: tuple[np.ndarray, np.ndarray, np.ndarray] | None = None,
        ai_reason: str | None = None,
    ) -> HistoryItem:
        if self.game_over:
            raise RuntimeError("ゲームは終了しています。")

        if cell in self.bombed_cells:
            raise ValueError("すでに爆撃済みのマスです。")

        self.bombed_cells.add(cell)

        result = self.judge_bomb(cell)
        sunk_id: int | None = None

        if result == "hit":
            if actor == "human":
                self.score_human += self.config.hit_score
            else:
                self.score_ai += self.config.hit_score

            sub = self.get_submarine_at(cell)
            if sub is not None:
                sunk_now = sub.register_hit(cell, actor)

                if sunk_now:
                    sunk_id = sub.id
                    if actor == "human":
                        self.score_human += self.config.sink_bonus
                    else:
                        self.score_ai += self.config.sink_bonus

        prob_map = info_map = score_map = None
        if ai_maps is not None:
            prob_map, info_map, score_map = ai_maps

        item = HistoryItem(
            turn=self.turn,
            action_index=self.action_index,
            actor=actor,
            x=cell[0],
            y=cell[1],
            result=result,
            score_human=self.score_human,
            score_ai=self.score_ai,
            sunk_submarine_id=sunk_id,
            is_bonus_action=is_bonus_action,
            ai_probability_map=prob_map.tolist() if prob_map is not None else None,
            ai_information_map=info_map.tolist() if info_map is not None else None,
            ai_score_map=score_map.tolist() if score_map is not None else None,
            ai_selected_reason=ai_reason,
        )

        self.history.append(item)
        self.action_index += 1

        if result == "hit":
            text = "直撃！"
        elif result == "near":
            text = "近い！ 強いソナー反応"
        elif result == "weak":
            text = "反応あり。弱いソナー反応"
        else:
            text = "反応なし"

        self.last_message = f"{'人間' if actor == 'human' else 'AI'}: {text}"

        if self.is_finished():
            self.game_over = True

        return item

    def human_bomb(self, cell: tuple[int, int]) -> HistoryItem:
        # 人間のクリック入力を最優先する。
        # ここではAIの確率マップ・情報量マップを計算しない。
        # 人間行動時のAIマップは，UI側で「AI思考中」と表示している間に
        # fill_ai_maps_for_history_item() を呼んで後から埋める。
        item = self.bomb(
            "human",
            cell,
            is_bonus_action=self.awaiting_human_bonus,
            ai_maps=None,
            ai_reason=None,
        )

        if (
            item.result == "hit"
            and self.config.human_hit_bonus
            and not self.awaiting_human_bonus
            and not self.game_over
        ):
            self.awaiting_human_bonus = True
        else:
            self.awaiting_human_bonus = False

        return item

    def fill_ai_maps_for_history_item(self, history_index: int) -> None:
        """指定した履歴項目に，その行動直前のAI推定マップを後から埋める。

        人間のクリック入力を即時表示するため，人間行動時には重いAI計算を行わない。
        その代わり，UI側で「AI思考中」と表示している間にこのメソッドを呼び，
        人間がクリックする直前の状態に基づくAI推定マップを履歴に保存する。

        history_index の行動そのものは，AI推定の入力から除外する。
        つまり，人間がクリックしたマスと結果をまだ知らない状態でのAI推定を保存する。
        """
        if history_index < 0 or history_index >= len(self.history):
            return

        item = self.history[history_index]

        if item.ai_probability_map is not None:
            return

        prior_history = self.history[:history_index]
        prior_bombed_cells = {(h.x, h.y) for h in prior_history}

        prob, info, score = self.ai.compute_maps(prior_history, prior_bombed_cells)

        item.ai_probability_map = prob.tolist()
        item.ai_information_map = info.tolist()
        item.ai_score_map = score.tolist()

        if item.actor == "human":
            item.ai_selected_reason = "このヒートマップは，人間がこのマスを爆撃する直前のAI推定です。"

    def ai_bomb(self) -> HistoryItem:
        x, y, prob, info, score, reason = self.ai.choose_action(
            self.history,
            self.bombed_cells,
        )

        return self.bomb(
            "ai",
            (x, y),
            ai_maps=(prob, info, score),
            ai_reason=reason,
        )

    def finish_turn_after_ai(self) -> None:
        if not self.game_over:
            self.turn += 1
            if self.is_finished():
                self.game_over = True

    def remaining_submarines(self) -> int:
        return sum(not sub.sunk for sub in self.submarines)

    def sunk_count(self) -> int:
        return sum(sub.sunk for sub in self.submarines)

    def winner_text(self) -> str:
        if self.score_human > self.score_ai:
            return "人間プレイヤーの勝ち"
        if self.score_ai > self.score_human:
            return "AIの勝ち"
        return "引き分け"