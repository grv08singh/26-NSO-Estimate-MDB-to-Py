# State names and codes
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

STATES: List[Tuple[str, int]] = [
    ("Jammu & Kashmir", 1),
    ("Himachal Pradesh", 2),
    ("Punjab", 3),
    ("Uttarakhand", 5),
    ("Haryana", 6),
    ("Rajasthan", 8),
    ("Uttar Pradesh", 9),
    ("Bihar", 10),
    ("Assam", 18),
    ("West Bengal", 19),
    ("Jharkhand", 20),
    ("Odisha", 21),
    ("Chhattisgarh", 22),
    ("Madhya Pradesh", 23),
    ("Gujarat", 24),
    ("Maharashtra", 27),
    ("Andhra Pradesh", 28),
    ("Karnataka", 29),
    ("Kerala", 32),
    ("Tamil Nadu", 33),
    ("Puducherry", 34),
    ("Telangana", 36),
]

_BY_CODE: Dict[int, str] = {c: n for n, c in STATES}
_BY_NAME: Dict[str, int] = {n: c for n, c in STATES}


# State name from code
def name_for_code(code: object) -> Optional[str]:
    try:
        return _BY_CODE.get(int(str(code).strip()))
    except (TypeError, ValueError):
        return None


def code_for_name(name: str) -> Optional[int]:
    return _BY_NAME.get(name)


def names() -> List[str]:
    return [n for n, _ in STATES]
