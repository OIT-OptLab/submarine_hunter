from dataclasses import dataclass


DIFFICULTY_SETTINGS = {
    "easy": {
        "label": "かんたん",
        "N": 8,
        "L": 3,
        "p": 2,
        "max_turns": 12,
    },
    "normal": {
        "label": "ふつう",
        "N": 10,
        "L": 3,
        "p": 3,
        "max_turns": 18,
    },
    "hard": {
        "label": "むずかしい",
        "N": 12,
        "L": 4,
        "p": 3,
        "max_turns": 24,
    },
}


@dataclass
class GameConfig:
    difficulty: str = "normal"
    N: int = 10
    L: int = 3
    p: int = 3

    near_distance: int = 3
    weak_distance: int = 5

    max_turns: int = 18
    hit_score: int = 1
    sink_bonus: int = 2

    human_hit_bonus: bool = True
    human_hit_bonus_chain: bool = False

    ai_alpha: float = 1.0
    ai_beta: float = 0.5

    # 展示中の応答性を保つため，AIが保持する候補配置数に上限を置く。
    # 値を大きくすると推定は安定するが，処理が重くなる。
    max_ai_candidates: int = 25000

    @classmethod
    def from_difficulty(cls, difficulty: str, human_hit_bonus: bool = True) -> "GameConfig":
        setting = DIFFICULTY_SETTINGS[difficulty]
        return cls(
            difficulty=difficulty,
            N=setting["N"],
            L=setting["L"],
            p=setting["p"],
            max_turns=setting["max_turns"],
            human_hit_bonus=human_hit_bonus,
        )
