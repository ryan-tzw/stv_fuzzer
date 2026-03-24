from __future__ import annotations

import json
import random
import string

from .service import GrammarService
from .spec import GrammarSpec, Production, lit, ref
from .tree import DerivationNode, literal


def _random_string_token() -> str:
    alphabet = string.ascii_letters + string.digits + " _-:/"
    length = random.randint(0, 12)
    value = "".join(random.choice(alphabet) for _ in range(length))
    return json.dumps(value, ensure_ascii=True)


def _random_number_token() -> str:
    choice = random.randrange(5)
    if choice == 0:
        return str(random.randint(-10, 10))
    if choice == 1:
        return str(random.randint(-10000, 10000))
    if choice == 2:
        return json.dumps(round(random.uniform(-1000, 1000), 3))
    if choice == 3:
        return f"{random.randint(-999, 999)}e{random.randint(-5, 5)}"
    return random.choice(["0", "1", "-1", "2147483647", "-2147483648"])


JSON_GRAMMAR = GrammarSpec(
    name="json",
    start_symbol="json",
    productions={
        "json": (Production((ref("value"),)),),
        "value": (
            Production((ref("object"),)),
            Production((ref("array"),)),
            Production((ref("string"),)),
            Production((ref("number"),)),
            Production((lit("true"),)),
            Production((lit("false"),)),
            Production((lit("null"),)),
        ),
        "object": (
            Production((lit("{"), lit("}"))),
            Production((lit("{"), ref("members"), lit("}"))),
        ),
        "members": (
            Production((ref("pair"),)),
            Production((ref("pair"), lit(","), ref("members"))),
        ),
        "pair": (Production((ref("string"), lit(":"), ref("value"))),),
        "array": (
            Production((lit("["), lit("]"))),
            Production((lit("["), ref("elements"), lit("]"))),
        ),
        "elements": (
            Production((ref("value"),)),
            Production((ref("value"), lit(","), ref("elements"))),
        ),
        "string": (Production((ref("STRING_TOKEN"),)),),
        "number": (Production((ref("NUMBER_TOKEN"),)),),
    },
    terminal_generators={
        "STRING_TOKEN": _random_string_token,
        "NUMBER_TOKEN": _random_number_token,
    },
    depth_limited_choices={
        "value": (2, 3, 4, 5, 6),
        "object": (0,),
        "array": (0,),
        "members": (0,),
        "elements": (0,),
    },
)


class JsonGrammarService(GrammarService):
    def __init__(self) -> None:
        super().__init__(JSON_GRAMMAR, max_depth=5)

    def parse(self, raw: str) -> DerivationNode | None:
        try:
            value = json.loads(raw)
        except TypeError:
            return None
        except ValueError:
            return None

        return DerivationNode(
            symbol="json",
            production_index=0,
            children=[self._build_value(value)],
        )

    def _build_value(self, value: object) -> DerivationNode:
        if isinstance(value, dict):
            return DerivationNode(
                symbol="value",
                production_index=0,
                children=[self._build_object(value)],
            )
        if isinstance(value, list):
            return DerivationNode(
                symbol="value",
                production_index=1,
                children=[self._build_array(value)],
            )
        if isinstance(value, str):
            return DerivationNode(
                symbol="value",
                production_index=2,
                children=[self._build_string(value)],
            )
        if isinstance(value, bool):
            text = "true" if value else "false"
            index = 4 if value else 5
            return DerivationNode(
                symbol="value",
                production_index=index,
                children=[literal(text)],
            )
        if value is None:
            return DerivationNode(
                symbol="value",
                production_index=6,
                children=[literal("null")],
            )
        return DerivationNode(
            symbol="value",
            production_index=3,
            children=[self._build_number(value)],
        )

    def _build_object(self, value: dict[object, object]) -> DerivationNode:
        items = [(str(key), val) for key, val in value.items()]
        if not items:
            return DerivationNode(
                symbol="object",
                production_index=0,
                children=[literal("{"), literal("}")],
            )
        return DerivationNode(
            symbol="object",
            production_index=1,
            children=[literal("{"), self._build_members(items), literal("}")],
        )

    def _build_members(self, items: list[tuple[str, object]]) -> DerivationNode:
        head, *tail = items
        if not tail:
            return DerivationNode(
                symbol="members",
                production_index=0,
                children=[self._build_pair(head)],
            )
        return DerivationNode(
            symbol="members",
            production_index=1,
            children=[
                self._build_pair(head),
                literal(","),
                self._build_members(tail),
            ],
        )

    def _build_pair(self, item: tuple[str, object]) -> DerivationNode:
        key, value = item
        return DerivationNode(
            symbol="pair",
            production_index=0,
            children=[
                self._build_string(key),
                literal(":"),
                self._build_value(value),
            ],
        )

    def _build_array(self, values: list[object]) -> DerivationNode:
        if not values:
            return DerivationNode(
                symbol="array",
                production_index=0,
                children=[literal("["), literal("]")],
            )
        return DerivationNode(
            symbol="array",
            production_index=1,
            children=[literal("["), self._build_elements(values), literal("]")],
        )

    def _build_elements(self, values: list[object]) -> DerivationNode:
        head, *tail = values
        if not tail:
            return DerivationNode(
                symbol="elements",
                production_index=0,
                children=[self._build_value(head)],
            )
        return DerivationNode(
            symbol="elements",
            production_index=1,
            children=[
                self._build_value(head),
                literal(","),
                self._build_elements(tail),
            ],
        )

    def _build_string(self, value: str) -> DerivationNode:
        return DerivationNode(
            symbol="string",
            production_index=0,
            children=[
                DerivationNode(
                    symbol="STRING_TOKEN",
                    text=json.dumps(value, ensure_ascii=True),
                )
            ],
        )

    def _build_number(self, value: object) -> DerivationNode:
        return DerivationNode(
            symbol="number",
            production_index=0,
            children=[
                DerivationNode(
                    symbol="NUMBER_TOKEN",
                    text=json.dumps(value, ensure_ascii=True),
                )
            ],
        )
