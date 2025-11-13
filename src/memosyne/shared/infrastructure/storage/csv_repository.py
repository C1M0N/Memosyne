"""CSV Repository for Reanimator v2 schema."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from ....reanimator.domain.models import TermInput, TermOutput

COLUMNS = [
    "WMPair",
    "WordEn",
    "MeanZh",
    "DefEn",
    "Example",
    "Rarity",
    "Field",
    "BatchNote",
    "IPA",
    "POS",
    "EtymoEn",
    "EtymoZh",
    "BatchId",
    "Picture",
    "WordId",
]


def _clean(value: str | None) -> str:
    return (value or "").strip()


class CSVTermRepository:
    @staticmethod
    def read_input(path: Path | str) -> list[TermInput]:
        path = Path(path)
        terms: list[TermInput] = []

        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            if not fieldnames or "WordEn" not in fieldnames or "MeanZh" not in fieldnames:
                raise ValueError("输入 CSV 必须包含 WordEn 和 MeanZh 列")

            for row in reader:
                word_en = _clean(row.get("WordEn"))
                mean_zh = _clean(row.get("MeanZh"))
                if not (word_en and mean_zh):
                    continue

                terms.append(
                    TermInput(
                        word_en=word_en,
                        mean_zh=mean_zh,
                        def_en=_clean(row.get("DefEn")),
                        example=_clean(row.get("Example")),
                        rarity=_clean(row.get("Rarity")),
                        field=_clean(row.get("Field")),
                        batch_note=_clean(row.get("BatchNote")),
                        ipa=_clean(row.get("IPA")),
                        pos=_clean(row.get("POS")),
                        etymo_en=_clean(row.get("EtymoEn")),
                        etymo_zh=_clean(row.get("EtymoZh")),
                        picture=_clean(row.get("Picture")),
                        word_id=_clean(row.get("WordId")) or None,
                    )
                )

        if not terms:
            raise ValueError("输入 CSV 没有有效的 WordEn / MeanZh 行")

        return terms

    @staticmethod
    def write_output(path: Path | str, terms: Iterable[TermOutput]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(COLUMNS)
            for term in terms:
                writer.writerow(term.to_csv_row())
