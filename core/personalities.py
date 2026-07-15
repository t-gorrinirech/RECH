import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"

PRIORITY_STRENGTH = 45.0
BACKGROUND_STRENGTH = 0.25


@dataclass
class ConnectorSymbols:
    symbols: List[dict]
    probability_of_appearance: float
    position: str
    probability_of_duplicate: float
    forced_only: bool


@dataclass
class Personality:
    personality_id: str
    display_name: str
    priority_mode: str
    priority_fields: List[str]
    primary_mode: str
    mode_leak_probability: float
    letter_substitution_probability: Dict[str, float]
    connector: ConnectorSymbols
    raw: dict = field(default_factory=dict)

    def _field_multiplier(self, origin: str) -> float:
        if self.priority_mode == "uniform_all_fields":
            return 1.0
        if origin in self.priority_fields:
            rank = self.priority_fields.index(origin)
            return PRIORITY_STRENGTH * float(len(self.priority_fields) - rank)
        return BACKGROUND_STRENGTH

    def compute_weights(self, tokens: List) -> List[float]:
        category_of = [token.origin.split(".", 1)[0] for token in tokens]
        fields_per_category = defaultdict(set)
        tokens_per_field = defaultdict(int)
        for token, category in zip(tokens, category_of):
            fields_per_category[category].add(token.origin)
            tokens_per_field[token.origin] += 1
        category_count = len(fields_per_category)
        weights = []
        for token, category in zip(tokens, category_of):
            base = (
                (1.0 / category_count)
                * (1.0 / len(fields_per_category[category]))
                * (1.0 / tokens_per_field[token.origin])
            )
            weights.append(base * self._field_multiplier(token.origin))
        return weights

    def symbol_pool(self) -> List[str]:
        return [entry["symbol"] for entry in self.connector.symbols]

    def symbol_weights(self) -> List[float]:
        return [float(entry.get("relative_weight", 1.0)) for entry in self.connector.symbols]


def available_personalities() -> List[str]:
    return sorted(path.stem for path in PROFILES_DIR.glob("*.json"))


def load_personality(personality_id: str) -> Personality:
    path = PROFILES_DIR / f"{personality_id}.json"
    if not path.exists():
        options = ", ".join(available_personalities())
        raise ValueError(f"unknown personality '{personality_id}'. available: {options}")
    data = json.loads(path.read_text(encoding="utf-8"))
    connector_data = data["connector_symbols"]
    connector = ConnectorSymbols(
        symbols=connector_data.get("symbols", []),
        probability_of_appearance=float(connector_data.get("probability_of_appearance", 0.0)),
        position=connector_data.get("position", "suffix_end"),
        probability_of_duplicate=float(connector_data.get("probability_of_duplicate", 0.0)),
        forced_only=bool(connector_data.get("forced_only", False)),
    )
    assembly = data.get("assembly", {})
    return Personality(
        personality_id=data["personality_id"],
        display_name=data.get("display_name", data["personality_id"]),
        priority_mode=data.get("priority_mode", "uniform_all_fields"),
        priority_fields=data.get("priority_fields", []),
        primary_mode=assembly.get("primary_mode", "human"),
        mode_leak_probability=float(assembly.get("mode_leak_probability", 0.0)),
        letter_substitution_probability=data.get("letter_substitution_probability", {}),
        connector=connector,
        raw=data,
    )
