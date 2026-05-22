from submarine_hunter.config import GameConfig
from submarine_hunter.game import SubmarineHunterGame


def test_game_can_start():
    config = GameConfig.from_difficulty("easy")
    game = SubmarineHunterGame(config, seed=0)
    assert len(game.submarines) == config.p
    assert len(game.all_submarine_cells()) == config.L * config.p


def test_bomb_result_values():
    config = GameConfig.from_difficulty("easy")
    game = SubmarineHunterGame(config, seed=0)
    result = game.judge_bomb((0, 0))
    assert result in {"hit", "near", "weak", "none"}
