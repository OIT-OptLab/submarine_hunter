from __future__ import annotations

import math
import sys
from dataclasses import dataclass

import pygame

from .config import GameConfig, DIFFICULTY_SETTINGS
from .game import SubmarineHunterGame
from .models import BombResult


WIDTH = 1120
HEIGHT = 760
FPS = 60

STATE_TITLE = "title"
STATE_PLAYING = "playing"
STATE_RESULT = "result"

COLOR_BG = (9, 24, 40)
COLOR_PANEL = (20, 37, 58)
COLOR_PANEL_2 = (28, 52, 77)
COLOR_TEXT = (235, 242, 250)
COLOR_MUTED = (160, 178, 195)
COLOR_ACCENT = (106, 198, 255)
COLOR_SEA = (17, 84, 126)
COLOR_SEA_2 = (15, 75, 114)
COLOR_GRID = (54, 130, 170)
COLOR_HIT = (255, 101, 66)
COLOR_HIT_CORE = (255, 220, 100)
COLOR_NEAR = (89, 255, 123)
COLOR_WEAK = (88, 220, 255)
COLOR_NONE = (156, 196, 215)
COLOR_SUB = (12, 22, 35)
COLOR_SUB_EDGE = (72, 91, 112)
COLOR_SUB_DIM = (10, 18, 29)
COLOR_WARNING = (255, 218, 76)
COLOR_HEAT_LOW = (25, 75, 160)
COLOR_HEAT_MID = (255, 220, 70)
COLOR_HEAT_HIGH = (255, 55, 45)

AI_DELAY_MS = 2000


@dataclass
class Button:
    rect: pygame.Rect
    label: str
    value: str | None = None


class App:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("AI潜水艦ハンター")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()

        self.font = self._load_font(22)
        self.small_font = self._load_font(17)
        self.large_font = self._load_font(42)
        self.mid_font = self._load_font(28)

        self.state = STATE_TITLE
        self.selected_difficulty = "normal"
        self.human_hit_bonus = True
        self.game: SubmarineHunterGame | None = None

        self.result_index = 0
        self.result_map_mode = "probability"

        self.pending_ai_at_ms: int | None = None
        self.pending_human_history_index: int | None = None

        self.title_buttons: list[Button] = []
        self._build_title_buttons()

    def _load_font(self, size: int) -> pygame.font.Font:
        candidates = [
            "Yu Gothic",
            "Meiryo",
            "MS Gothic",
            "Noto Sans CJK JP",
            "Hiragino Sans",
            "Arial Unicode MS",
        ]
        for name in candidates:
            path = pygame.font.match_font(name)
            if path:
                return pygame.font.Font(path, size)
        return pygame.font.SysFont(None, size)

    def _build_title_buttons(self) -> None:
        self.title_buttons = []
        x = 405
        y = 280
        w = 300
        h = 56
        gap = 16

        for key in ["easy", "normal", "hard"]:
            label = DIFFICULTY_SETTINGS[key]["label"]
            self.title_buttons.append(Button(pygame.Rect(x, y, w, h), label, key))
            y += h + gap

        self.title_buttons.append(Button(pygame.Rect(x, y + 10, w, h), "直撃ボーナス ON/OFF", "bonus"))
        self.title_buttons.append(Button(pygame.Rect(x, y + 92, w, 66), "START", "start"))

    def run(self) -> None:
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            for event in pygame.event.get():
                self.handle_event(event)

            self.update()
            self.draw(dt)
            pygame.display.flip()

    def update(self) -> None:
        if self.state != STATE_PLAYING:
            return
        if self.game is None:
            return
        if self.pending_ai_at_ms is None:
            return

        now = pygame.time.get_ticks()

        # 最低2秒はAIの爆撃を表示しない。
        if now < self.pending_ai_at_ms:
            return

        # AI思考中の間に，人間の直前行動に対するAI推定マップを後から埋める。
        # このとき，人間の直前行動そのものは推定入力から除外される。
        if self.pending_human_history_index is not None:
            self.game.fill_ai_maps_for_history_item(self.pending_human_history_index)
            self.pending_human_history_index = None

        self.pending_ai_at_ms = None

        if self.game.game_over:
            self.state = STATE_RESULT
            self.result_index = max(0, len(self.game.history) - 1)
            return

        self.game.ai_bomb()
        self.game.finish_turn_after_ai()

        if self.game.game_over:
            self.state = STATE_RESULT
            self.result_index = max(0, len(self.game.history) - 1)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

        if self.state == STATE_TITLE:
            self.handle_title_event(event)
        elif self.state == STATE_PLAYING:
            self.handle_playing_event(event)
        elif self.state == STATE_RESULT:
            self.handle_result_event(event)

    def handle_title_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return

        pos = event.pos
        for button in self.title_buttons:
            if button.rect.collidepoint(pos):
                if button.value in {"easy", "normal", "hard"}:
                    self.selected_difficulty = button.value
                elif button.value == "bonus":
                    self.human_hit_bonus = not self.human_hit_bonus
                elif button.value == "start":
                    config = GameConfig.from_difficulty(self.selected_difficulty, self.human_hit_bonus)
                    self.game = SubmarineHunterGame(config)
                    self.pending_ai_at_ms = None
                    self.pending_human_history_index = None
                    self.state = STATE_PLAYING
                return

    def handle_playing_event(self, event: pygame.event.Event) -> None:
        if self.game is None:
            return

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            pygame.quit()
            sys.exit()

        if self.game.game_over:
            self.state = STATE_RESULT
            self.result_index = max(0, len(self.game.history) - 1)
            return

        # AI思考中は，人間のクリックを受け付けない。
        # ただし，人間の爆撃結果はこの待機に入る前に即時表示される。
        if self.pending_ai_at_ms is not None:
            return

        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return

        cell = self.screen_to_cell(event.pos)
        if cell is None:
            return

        try:
            self.game.human_bomb(cell)
        except ValueError:
            self.game.last_message = "そのマスはすでに爆撃済みです"
            return

        human_history_index = len(self.game.history) - 1

        if self.game.game_over:
            self.state = STATE_RESULT
            self.result_index = max(0, len(self.game.history) - 1)
            return

        # 直撃ボーナス待ちならAIはまだ動かない。
        if self.game.awaiting_human_bonus:
            self.game.last_message += " 追加爆撃できます"
            return

        # 人間の爆撃結果はすぐ表示する。
        # AIの推定計算と爆撃は，最低2秒後に行う。
        self.pending_human_history_index = human_history_index
        self.pending_ai_at_ms = pygame.time.get_ticks() + AI_DELAY_MS
        self.game.last_message += " / AI思考中..."

    def handle_result_event(self, event: pygame.event.Event) -> None:
        if self.game is None:
            return

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                pygame.quit()
                sys.exit()
            if event.key == pygame.K_r:
                self.state = STATE_TITLE
                self.game = None
                self.pending_ai_at_ms = None
                self.pending_human_history_index = None
            if event.key == pygame.K_RIGHT:
                self.result_index = min(len(self.game.history) - 1, self.result_index + 1)
            if event.key == pygame.K_LEFT:
                self.result_index = max(0, self.result_index - 1)
            if event.key == pygame.K_1:
                self.result_map_mode = "probability"
            if event.key == pygame.K_2:
                self.result_map_mode = "information"
            if event.key == pygame.K_3:
                self.result_map_mode = "score"

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            bar = pygame.Rect(80, 710, 620, 18)
            if bar.collidepoint(event.pos) and self.game.history:
                ratio = (event.pos[0] - bar.x) / bar.width
                self.result_index = int(ratio * (len(self.game.history) - 1))

    def board_layout(self) -> tuple[int, int, int]:
        if self.game is None:
            return 60, 120, 48
        N = self.game.config.N
        tile = min(52, int(610 / N))
        left = 60
        top = 100
        return left, top, tile

    def screen_to_cell(self, pos: tuple[int, int]) -> tuple[int, int] | None:
        if self.game is None:
            return None

        left, top, tile = self.board_layout()
        x, y = pos
        col = (x - left) // tile
        row = (y - top) // tile

        if 0 <= col < self.game.config.N and 0 <= row < self.game.config.N:
            return int(col), int(row)

        return None

    def draw(self, dt: float) -> None:
        self.screen.fill(COLOR_BG)

        if self.state == STATE_TITLE:
            self.draw_title()
        elif self.state == STATE_PLAYING:
            self.draw_playing()
        elif self.state == STATE_RESULT:
            self.draw_result()

    def draw_text(
        self,
        text: str,
        pos: tuple[int, int],
        font: pygame.font.Font | None = None,
        color=COLOR_TEXT,
    ) -> None:
        font = font or self.font
        surface = font.render(text, True, color)
        self.screen.blit(surface, pos)

    def draw_centered_text(
        self,
        text: str,
        rect: pygame.Rect,
        font: pygame.font.Font | None = None,
        color=COLOR_TEXT,
    ) -> None:
        font = font or self.font
        surface = font.render(text, True, color)
        self.screen.blit(surface, surface.get_rect(center=rect.center))

    def draw_title(self) -> None:
        self.draw_centered_text("AI潜水艦ハンター", pygame.Rect(0, 90, WIDTH, 70), self.large_font)
        self.draw_centered_text(
            "ベイズ推定で見えない潜水艦を探す展示ゲーム",
            pygame.Rect(0, 158, WIDTH, 40),
            self.font,
            COLOR_MUTED,
        )

        for button in self.title_buttons:
            selected = button.value == self.selected_difficulty
            color = COLOR_ACCENT if selected else COLOR_PANEL_2

            if button.value == "bonus":
                color = COLOR_ACCENT if self.human_hit_bonus else COLOR_PANEL_2
                label = f"直撃ボーナス: {'ON' if self.human_hit_bonus else 'OFF'}"
            elif button.value == "start":
                color = COLOR_HIT
                label = "START"
            else:
                label = button.label

            pygame.draw.rect(self.screen, color, button.rect, border_radius=14)
            pygame.draw.rect(self.screen, (180, 220, 240), button.rect, width=2, border_radius=14)
            self.draw_centered_text(label, button.rect, self.font, COLOR_TEXT)

        self.draw_centered_text(
            "難易度を選び，STARTを押してください",
            pygame.Rect(0, 660, WIDTH, 30),
            self.small_font,
            COLOR_MUTED,
        )
        self.draw_text(
            "難易度の説明",
            (820, 220),
            self.font,
             COLOR_ACCENT,
        )

        self.draw_text(
            "かんたん : 6×6マス ・ 潜水艦2隻",
            (820, 260),
            self.small_font,
        )

        self.draw_text(
            "ふつう : 8×8マス ・ 潜水艦3隻",
            (820, 300),
            self.small_font,
        )

        self.draw_text(
            "むずかしい : 10×10マス ・ 潜水艦4隻",
            (820, 340),
            self.small_font,
        )
        # 得点説明
        self.draw_text(
            "得点ルール",
            (820, 420),
            self.font,
            COLOR_ACCENT,
        )

        self.draw_text(
            "潜水艦を直撃 : +1点",
            (820, 460),
            self.small_font,
        )

        self.draw_text(
            "潜水艦を撃沈 : +2点",
            (820, 495),
            self.small_font,
        )

        self.draw_text(
            "より高得点の方が勝利",
            (820, 530),
            self.small_font,
        )

    def draw_playing(self) -> None:
        assert self.game is not None

        self.draw_text("AI潜水艦ハンター", (60, 36), self.mid_font)

        latest_index = len(self.game.history) - 1 if self.game.history else None

        self.draw_board(
            show_submarines=False,
            selected_history=latest_index,
            history_upto=None,
        )

        self.draw_sidebar()
        self.draw_legend(760, 500)

    def draw_sidebar(self) -> None:
        assert self.game is not None

        panel = pygame.Rect(740, 90, 330, 385)
        pygame.draw.rect(self.screen, COLOR_PANEL, panel, border_radius=18)

        g = self.game
        y = 116

        self.draw_text(f"ターン: {min(g.turn, g.config.max_turns)} / {g.config.max_turns}", (770, y), self.font)
        y += 42
        self.draw_text(f"人間: {g.score_human} 点", (770, y), self.font, COLOR_NEAR)
        y += 42
        self.draw_text(f"AI: {g.score_ai} 点", (770, y), self.font, COLOR_ACCENT)
        y += 42
        self.draw_text(f"撃沈数: {g.sunk_count()} / {g.config.p}", (770, y), self.font)
        y += 42

        if self.pending_ai_at_ms is not None:
            self.draw_text("AI思考中...", (770, y), self.font, COLOR_WARNING)
        elif g.awaiting_human_bonus:
            self.draw_text("追加爆撃できます", (770, y), self.font, COLOR_WARNING)
        else:
            self.draw_text("未爆撃マスをクリック", (770, y), self.font, COLOR_MUTED)

        y += 54

        pygame.draw.rect(self.screen, COLOR_PANEL_2, pygame.Rect(765, y, 280, 96), border_radius=12)
        self.draw_wrapped_text(g.last_message, (785, y + 18), 245, self.small_font, COLOR_TEXT)

    def draw_board(
        self,
        show_submarines: bool,
        selected_history: int | None,
        history_upto: int | None,
    ) -> None:
        assert self.game is not None

        g = self.game
        N = g.config.N
        left, top, tile = self.board_layout()

        self.draw_sea_grid(left, top, tile, N)

        # 船影は背面に描く。
        # ゲーム中は撃沈済みのみ，結果画面では全艦を表示する。
        for sub in g.submarines:
            if show_submarines or sub.sunk:
                self.draw_submarine(sub, left, top, tile, force_show=show_submarines)

        visible_history = g.history if history_upto is None else g.history[:history_upto]

        # 爆撃結果は船影の上に描く。
        sunk_cells = self.get_sunk_cells()

        for idx, item in enumerate(visible_history):
            rect = pygame.Rect(left + item.x * tile, top + item.y * tile, tile - 2, tile - 2)

            alpha = 150 if item.result == "hit" and (item.x, item.y) in sunk_cells else 255

            self.draw_result_icon(
                rect,
                item.result,
                is_selected=False,
                alpha=alpha,
            )

        # 最新手を黄色枠で強調する。
        if selected_history is not None and 0 <= selected_history < len(g.history):
            item = g.history[selected_history]
            if history_upto is None or selected_history < history_upto:
                rect = pygame.Rect(left + item.x * tile, top + item.y * tile, tile - 2, tile - 2)
                self.draw_latest_highlight(rect)

        for i in range(N + 1):
            pygame.draw.line(self.screen, COLOR_GRID, (left, top + i * tile), (left + N * tile, top + i * tile), 1)
            pygame.draw.line(self.screen, COLOR_GRID, (left + i * tile, top), (left + i * tile, top + N * tile), 1)

    def draw_sea_grid(self, left: int, top: int, tile: int, N: int) -> None:
        for row in range(N):
            for col in range(N):
                rect = pygame.Rect(left + col * tile, top + row * tile, tile - 2, tile - 2)
                base = COLOR_SEA if (row + col) % 2 == 0 else COLOR_SEA_2
                pygame.draw.rect(self.screen, base, rect, border_radius=4)

                inner = rect.inflate(-8, -8)
                if inner.width > 0 and inner.height > 0:
                    pygame.draw.rect(
                        self.screen,
                        (base[0] + 8, base[1] + 10, base[2] + 12),
                        inner,
                        border_radius=4,
                    )

    def draw_result_icon(
        self,
        rect: pygame.Rect,
        result: BombResult,
        is_selected: bool = False,
        alpha: int = 255,
    ) -> None:
        surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)

        cx = rect.width // 2
        cy = rect.height // 2
        radius = max(7, rect.width // 4)

        def with_alpha(color: tuple[int, int, int]) -> tuple[int, int, int, int]:
            return (color[0], color[1], color[2], alpha)

        if result == "hit":
            pygame.draw.circle(surface, with_alpha(COLOR_HIT), (cx, cy), radius + 5)
            pygame.draw.circle(surface, with_alpha(COLOR_HIT_CORE), (cx, cy), radius)

            for angle in range(0, 360, 45):
                rad = math.radians(angle)
                x1 = cx + int(math.cos(rad) * (radius - 2))
                y1 = cy + int(math.sin(rad) * (radius - 2))
                x2 = cx + int(math.cos(rad) * (radius + 10))
                y2 = cy + int(math.sin(rad) * (radius + 10))
                pygame.draw.line(
                    surface,
                    (255, 240, 185, alpha),
                    (x1, y1),
                    (x2, y2),
                    3,
                )

        elif result == "near":
            pygame.draw.circle(surface, with_alpha(COLOR_NEAR), (cx, cy), radius + 8, 3)
            pygame.draw.circle(surface, with_alpha(COLOR_NEAR), (cx, cy), radius, 2)
            pygame.draw.circle(surface, with_alpha(COLOR_NEAR), (cx, cy), 4)

        elif result == "weak":
            pygame.draw.circle(surface, with_alpha(COLOR_WEAK), (cx, cy), radius + 4, 2)
            pygame.draw.circle(surface, with_alpha(COLOR_WEAK), (cx, cy), max(3, radius - 5), 1)

        elif result == "none":
            pygame.draw.circle(surface, with_alpha(COLOR_NONE), (cx, cy), 4)
            pygame.draw.circle(surface, with_alpha(COLOR_NONE), (cx, cy), radius, 1)

        self.screen.blit(surface, rect.topleft)

        if is_selected:
            self.draw_latest_highlight(rect)


    def draw_latest_highlight(self, rect: pygame.Rect) -> None:
        outer = rect.inflate(-2, -2)
        pygame.draw.rect(self.screen, COLOR_WARNING, outer, width=4, border_radius=5)

    def draw_submarine(self, sub, left: int, top: int, tile: int, force_show: bool) -> None:
        cells = sorted(sub.cells, key=lambda c: (c[1], c[0]))
        horizontal = sub.orientation == "horizontal"

        if not horizontal:
            cells = sorted(sub.cells, key=lambda c: (c[0], c[1]))

        body_color = COLOR_SUB if force_show else COLOR_SUB_DIM
        edge_color = COLOR_SUB_EDGE if force_show else (45, 62, 80)

        for i, (x, y) in enumerate(cells):
            rect = pygame.Rect(left + x * tile + 5, top + y * tile + 5, tile - 12, tile - 12)

            if horizontal:
                if i == 0:
                    points = [(rect.right, rect.top), (rect.right, rect.bottom), (rect.left, rect.centery)]
                elif i == len(cells) - 1:
                    points = [(rect.left, rect.top), (rect.left, rect.bottom), (rect.right, rect.centery)]
                else:
                    points = [
                        (rect.left, rect.top),
                        (rect.right, rect.top),
                        (rect.right, rect.bottom),
                        (rect.left, rect.bottom),
                    ]
            else:
                if i == 0:
                    points = [(rect.left, rect.bottom), (rect.right, rect.bottom), (rect.centerx, rect.top)]
                elif i == len(cells) - 1:
                    points = [(rect.left, rect.top), (rect.right, rect.top), (rect.centerx, rect.bottom)]
                else:
                    points = [
                        (rect.left, rect.top),
                        (rect.right, rect.top),
                        (rect.right, rect.bottom),
                        (rect.left, rect.bottom),
                    ]

            pygame.draw.polygon(self.screen, body_color, points)
            pygame.draw.polygon(self.screen, edge_color, points, width=2)

            if i == len(cells) // 2:
                tower = rect.inflate(-rect.width // 2, -rect.height // 2)
                pygame.draw.ellipse(self.screen, edge_color, tower)

    def draw_submarine_legend_icon(self, rect: pygame.Rect) -> None:
        part_w = rect.width // 3
        y = rect.y + 8
        h = rect.height - 16

        head = pygame.Rect(rect.x, y, part_w, h)
        body = pygame.Rect(rect.x + part_w, y, part_w, h)
        tail = pygame.Rect(rect.x + part_w * 2, y, part_w, h)

        head_points = [(head.right, head.top), (head.right, head.bottom), (head.left, head.centery)]
        body_points = [
            (body.left, body.top),
            (body.right, body.top),
            (body.right, body.bottom),
            (body.left, body.bottom),
        ]
        tail_points = [(tail.left, tail.top), (tail.left, tail.bottom), (tail.right, tail.centery)]

        for points in [head_points, body_points, tail_points]:
            pygame.draw.polygon(self.screen, COLOR_SUB, points)
            pygame.draw.polygon(self.screen, COLOR_SUB_EDGE, points, width=2)

        tower = pygame.Rect(body.centerx - 5, body.centery - 5, 10, 10)
        pygame.draw.ellipse(self.screen, COLOR_SUB_EDGE, tower)

    def draw_legend(self, x: int, y: int) -> None:
        panel = pygame.Rect(x - 20, y - 18, 300, 240)
        pygame.draw.rect(self.screen, COLOR_PANEL, panel, border_radius=16)
        self.draw_text("凡例", (x, y), self.small_font, COLOR_MUTED)

        items = [
            ("直撃", "hit"),
            ("近い", "near"),
            ("反応あり", "weak"),
            ("反応なし", "none"),
            ("撃沈艦影", "sub"),
            ("最新の爆撃", "latest"),
        ]

        yy = y + 30
        for label, kind in items:
            rect = pygame.Rect(x, yy, 36, 30)

            if kind == "sub":
                self.draw_submarine_legend_icon(rect)
            elif kind == "latest":
                pygame.draw.rect(self.screen, COLOR_SEA, rect, border_radius=4)
                self.draw_latest_highlight(rect)
            else:
                self.draw_result_icon(rect, kind)  # type: ignore[arg-type]

            self.draw_text(label, (x + 52, yy + 5), self.small_font)
            yy += 29

    def draw_result(self) -> None:
        assert self.game is not None

        g = self.game

        self.draw_text("結果画面", (60, 30), self.mid_font)
        self.draw_text(f"{g.winner_text()}  人間 {g.score_human} 点 / AI {g.score_ai} 点", (60, 68), self.font)

        history_item = g.history[self.result_index] if g.history else None

        # 左側は結果盤面。
        # 履歴表示では，その行動までの爆撃結果のみ表示する。
        self.draw_board(
            show_submarines=True,
            selected_history=self.result_index,
            history_upto=self.result_index + 1,
        )

        # 右側にヒートマップを別表示する。
        # 盤面には重ねない。
        heatmap = None
        mode_text = ""

        if history_item is not None:
            if self.result_map_mode == "probability":
                heatmap = history_item.ai_probability_map
                mode_text = "潜水艦存在確率"
            elif self.result_map_mode == "information":
                heatmap = history_item.ai_information_map
                mode_text = "期待情報量"
            else:
                heatmap = history_item.ai_score_map
                mode_text = "AI評価値"

        self.draw_heatmap_panel(735, 92, 320, 320, heatmap, mode_text, history_item)

        panel = pygame.Rect(735, 430, 340, 280)
        pygame.draw.rect(self.screen, COLOR_PANEL, panel, border_radius=18)

        y = 454

        if history_item is not None:
            actor = "人間" if history_item.actor == "human" else "AI"

            self.draw_text(f"行動 {history_item.action_index} / {len(g.history)}", (760, y), self.small_font)
            y += 25
            self.draw_text(f"ターン: {history_item.turn}", (760, y), self.small_font)
            y += 25
            self.draw_text(f"行動者: {actor}", (760, y), self.small_font)
            y += 25
            self.draw_text(f"爆撃: ({history_item.x}, {history_item.y})", (760, y), self.small_font)
            y += 25
            self.draw_text(f"結果: {self.result_label(history_item.result)}", (760, y), self.small_font)
            y += 25
            self.draw_text(f"得点: 人間 {history_item.score_human} / AI {history_item.score_ai}", (760, y), self.small_font)
            y += 32

            if history_item.ai_probability_map is not None:
                py = history_item.y
                px = history_item.x
                p_hit = history_item.ai_probability_map[py][px]
                h_val = history_item.ai_information_map[py][px] if history_item.ai_information_map else 0
                s_val = history_item.ai_score_map[py][px] if history_item.ai_score_map else 0

                self.draw_text(f"直撃確率: {p_hit:.2f}", (760, y), self.small_font, COLOR_NEAR)
                y += 24
                self.draw_text(f"期待情報量: {h_val:.2f}", (760, y), self.small_font, COLOR_WEAK)
                y += 24
                self.draw_text(f"評価値: {s_val:.2f}", (760, y), self.small_font, COLOR_WARNING)

        self.draw_text("←/→ 履歴移動   1/2/3 表示切替   R タイトルへ", (60, 675), self.small_font, COLOR_MUTED)
        self.draw_history_bar()

    def draw_heatmap_panel(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        heatmap: list[list[float]] | None,
        title: str,
        history_item,
    ) -> None:
        assert self.game is not None

        g = self.game

        panel = pygame.Rect(x, y, w, h)
        pygame.draw.rect(self.screen, COLOR_PANEL, panel, border_radius=18)

        self.draw_text(title, (x + 20, y + 14), self.font)
        self.draw_text("1:確率  2:情報量  3:評価値", (x + 20, y + 45), self.small_font, COLOR_MUTED)

        if heatmap is None:
            self.draw_centered_text("ヒートマップなし", panel, self.small_font, COLOR_MUTED)
            return

        N = g.config.N
        grid_size = min(w - 58, h - 100)
        tile = grid_size // N
        left = x + 24
        top = y + 78

        values = [v for row in heatmap for v in row]
        max_v = max(values) if values else 0.0
        min_v = min(values) if values else 0.0

        # 色の強弱が見えるように，表示時だけ正規化する。
        denom = max_v - min_v
        if denom < 1e-9:
            denom = 1.0

        for row in range(N):
            for col in range(N):
                raw = heatmap[row][col]
                value = (raw - min_v) / denom
                value = max(0.0, min(1.0, value))

                color = self.heat_color(value)
                rect = pygame.Rect(left + col * tile, top + row * tile, tile - 1, tile - 1)
                pygame.draw.rect(self.screen, color, rect)

        for i in range(N + 1):
            pygame.draw.line(self.screen, (35, 55, 75), (left, top + i * tile), (left + N * tile, top + i * tile), 1)
            pygame.draw.line(self.screen, (35, 55, 75), (left + i * tile, top), (left + i * tile, top + N * tile), 1)

        if history_item is not None:
            rect = pygame.Rect(left + history_item.x * tile, top + history_item.y * tile, tile - 1, tile - 1)
            self.draw_latest_highlight(rect)

        # カラーバー
        bar_x = left + N * tile + 14
        bar_y = top
        bar_h = N * tile

        for i in range(bar_h):
            v = 1.0 - i / max(1, bar_h - 1)
            color = self.heat_color(v)
            pygame.draw.line(self.screen, color, (bar_x, bar_y + i), (bar_x + 16, bar_y + i))

        self.draw_text("高", (bar_x + 22, bar_y - 3), self.small_font, COLOR_TEXT)
        self.draw_text("低", (bar_x + 22, bar_y + bar_h - 16), self.small_font, COLOR_TEXT)

    def heat_color(self, value: float) -> tuple[int, int, int]:
        value = max(0.0, min(1.0, value))

        # 低:青 → 中:黄 → 高:赤
        if value < 0.5:
            t = value / 0.5
            return self.mix_color(COLOR_HEAT_LOW, COLOR_HEAT_MID, t)

        t = (value - 0.5) / 0.5
        return self.mix_color(COLOR_HEAT_MID, COLOR_HEAT_HIGH, t)

    def mix_color(
        self,
        a: tuple[int, int, int],
        b: tuple[int, int, int],
        t: float,
    ) -> tuple[int, int, int]:
        return (
            int(a[0] * (1 - t) + b[0] * t),
            int(a[1] * (1 - t) + b[1] * t),
            int(a[2] * (1 - t) + b[2] * t),
        )

    def draw_history_bar(self) -> None:
        assert self.game is not None

        bar = pygame.Rect(80, 710, 620, 18)
        pygame.draw.rect(self.screen, COLOR_PANEL_2, bar, border_radius=9)

        if not self.game.history:
            return

        ratio = self.result_index / max(1, len(self.game.history) - 1)
        knob_x = int(bar.x + ratio * bar.width)
        pygame.draw.circle(self.screen, COLOR_WARNING, (knob_x, bar.centery), 10)

    def draw_wrapped_text(
        self,
        text: str,
        pos: tuple[int, int],
        width: int,
        font: pygame.font.Font,
        color,
    ) -> None:
        x, y = pos
        line = ""

        for ch in text:
            test = line + ch
            if font.size(test)[0] > width:
                self.draw_text(line, (x, y), font, color)
                y += font.get_height() + 4
                line = ch
            else:
                line = test

        if line:
            self.draw_text(line, (x, y), font, color)

    def result_label(self, result: BombResult) -> str:
        return {
            "hit": "直撃",
            "near": "近い",
            "weak": "反応あり",
            "none": "反応なし",
        }[result]

    def get_sunk_cells(self) -> set[tuple[int, int]]:
        if self.game is None:
            return set()

        cells: set[tuple[int, int]] = set()
        for sub in self.game.submarines:
            if sub.sunk:
                cells.update(sub.cells)

        return cells

def run_app() -> None:
    App().run()