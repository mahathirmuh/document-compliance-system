"""Measurement consistency using aliases, without automatic conversion."""

from __future__ import annotations

import re
from collections import Counter
from decimal import Decimal

from app.models.similarity_enums import ConsistencyStatus
from app.schemas.similarity_internal import ConsistencyCheckResult

_ALIASES: dict[str, tuple[str, str]] = {
    "mm": ("length", "mm"),
    "millimeter": ("length", "mm"),
    "millimeters": ("length", "mm"),
    "毫米": ("length", "mm"),
    "cm": ("length", "cm"),
    "centimeter": ("length", "cm"),
    "centimeters": ("length", "cm"),
    "厘米": ("length", "cm"),
    "m": ("length", "m"),
    "meter": ("length", "m"),
    "meters": ("length", "m"),
    "metre": ("length", "m"),
    "米": ("length", "m"),
    "km": ("length", "km"),
    "kilometer": ("length", "km"),
    "kilometers": ("length", "km"),
    "公里": ("length", "km"),
    "g": ("weight", "g"),
    "gram": ("weight", "g"),
    "grams": ("weight", "g"),
    "克": ("weight", "g"),
    "kg": ("weight", "kg"),
    "kilogram": ("weight", "kg"),
    "kilograms": ("weight", "kg"),
    "kilogramme": ("weight", "kg"),
    "千克": ("weight", "kg"),
    "公斤": ("weight", "kg"),
    "ml": ("volume", "ml"),
    "milliliter": ("volume", "ml"),
    "milliliters": ("volume", "ml"),
    "毫升": ("volume", "ml"),
    "l": ("volume", "l"),
    "liter": ("volume", "l"),
    "liters": ("volume", "l"),
    "litre": ("volume", "l"),
    "升": ("volume", "l"),
    "°c": ("temperature", "c"),
    "celsius": ("temperature", "c"),
    "摄氏度": ("temperature", "c"),
    "kpa": ("pressure", "kpa"),
    "mpa": ("pressure", "mpa"),
    "bar": ("pressure", "bar"),
    "v": ("voltage", "v"),
    "volt": ("voltage", "v"),
    "伏": ("voltage", "v"),
    "a": ("current", "a"),
    "ampere": ("current", "a"),
    "安培": ("current", "a"),
    "s": ("duration", "s"),
    "second": ("duration", "s"),
    "seconds": ("duration", "s"),
    "detik": ("duration", "s"),
    "秒": ("duration", "s"),
    "minute": ("duration", "min"),
    "minutes": ("duration", "min"),
    "menit": ("duration", "min"),
    "分钟": ("duration", "min"),
    "hour": ("duration", "h"),
    "hours": ("duration", "h"),
    "jam": ("duration", "h"),
    "小时": ("duration", "h"),
    "day": ("duration", "day"),
    "days": ("duration", "day"),
    "hari": ("duration", "day"),
    "天": ("duration", "day"),
    "%": ("percentage", "%"),
    "percent": ("percentage", "%"),
    "persen": ("percentage", "%"),
}
_UNIT_PATTERN = "|".join(
    re.escape(value)
    for value in sorted(_ALIASES, key=len, reverse=True)
)
_MEASUREMENT_RE = re.compile(
    rf"(?<!\d)(?<![A-Za-z_])(?P<number>[-+]?\d+(?:[.,]\d+)?)\s*"
    rf"(?P<unit>{_UNIT_PATTERN})(?![A-Za-z])",
    re.IGNORECASE,
)
_BASE_FACTORS: dict[tuple[str, str], Decimal] = {
    ("length", "mm"): Decimal("0.001"),
    ("length", "cm"): Decimal("0.01"),
    ("length", "m"): Decimal(1),
    ("length", "km"): Decimal(1000),
    ("weight", "g"): Decimal("0.001"),
    ("weight", "kg"): Decimal(1),
    ("volume", "ml"): Decimal("0.001"),
    ("volume", "l"): Decimal(1),
    ("pressure", "kpa"): Decimal(1),
    ("pressure", "mpa"): Decimal(1000),
    ("pressure", "bar"): Decimal(100),
    ("duration", "s"): Decimal(1),
    ("duration", "min"): Decimal(60),
    ("duration", "h"): Decimal(3600),
    ("duration", "day"): Decimal(86400),
    ("temperature", "c"): Decimal(1),
    ("voltage", "v"): Decimal(1),
    ("current", "a"): Decimal(1),
    ("percentage", "%"): Decimal(1),
}


class MeasurementConsistencyService:
    def check(
        self, source_text: str, target_text: str
    ) -> ConsistencyCheckResult:
        source = self.extract(source_text)
        target = self.extract(target_text)
        source_values = [item[2] for item in source]
        target_values = [item[2] for item in target]
        if not source and not target:
            status = ConsistencyStatus.NOT_APPLICABLE
        elif Counter(source_values) == Counter(target_values):
            status = ConsistencyStatus.MATCH
        elif self._potentially_equivalent(source, target):
            status = ConsistencyStatus.POTENTIALLY_EQUIVALENT
        else:
            status = ConsistencyStatus.MISMATCH
        return ConsistencyCheckResult(
            status=status,
            source_values=source_values,
            target_values=target_values,
            details={
                "sourceMeasurements": [
                    {"dimension": dimension, "unit": unit, "value": value}
                    for dimension, unit, value in source
                ],
                "targetMeasurements": [
                    {"dimension": dimension, "unit": unit, "value": value}
                    for dimension, unit, value in target
                ],
                "conversionApplied": False,
            },
        )

    def extract(self, text: str) -> list[tuple[str, str, str]]:
        output: list[tuple[str, str, str]] = []
        for match in _MEASUREMENT_RE.finditer(text):
            unit_raw = match.group("unit").casefold()
            dimension, unit = _ALIASES[unit_raw]
            value = str(
                Decimal(match.group("number").replace(",", ".")).normalize()
            )
            output.append((dimension, unit, f"{value} {unit}"))
        return output

    @staticmethod
    def _potentially_equivalent(
        source: list[tuple[str, str, str]],
        target: list[tuple[str, str, str]],
    ) -> bool:
        if not source or len(source) != len(target):
            return False
        source_items = sorted(source, key=lambda item: (item[0], item[1]))
        target_items = sorted(target, key=lambda item: (item[0], item[1]))
        used_different_unit = False
        for source_item, target_item in zip(
            source_items, target_items, strict=True
        ):
            source_dimension, source_unit, source_value = source_item
            target_dimension, target_unit, target_value = target_item
            if source_dimension != target_dimension:
                return False
            source_factor = _BASE_FACTORS.get(
                (source_dimension, source_unit)
            )
            target_factor = _BASE_FACTORS.get(
                (target_dimension, target_unit)
            )
            if source_factor is None or target_factor is None:
                return False
            source_number = Decimal(source_value.split(" ", 1)[0])
            target_number = Decimal(target_value.split(" ", 1)[0])
            if source_number * source_factor != target_number * target_factor:
                return False
            used_different_unit = (
                used_different_unit or source_unit != target_unit
            )
        return used_different_unit
