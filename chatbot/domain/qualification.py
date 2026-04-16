from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DisqualificationReason(StrEnum):
    HOTEL_CHAIN = "hotel_chain"
    TOURIST = "tourist"
    AGENCY = "agency"
    LOW_VOLUME = "low_volume"
    OTHER = "other"


@dataclass(slots=True)
class QualificationAnswers:
    phase_2_answer_1: str | None = None
    phase_2_answer_2: str | None = None
    phase_2_answer_3: str | None = None
    phase_2_answer_4: str | None = None
    phase_2_answer_5: str | None = None
    phase_2_answer_6: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "phase_2_answer_1": self.phase_2_answer_1,
            "phase_2_answer_2": self.phase_2_answer_2,
            "phase_2_answer_3": self.phase_2_answer_3,
            "phase_2_answer_4": self.phase_2_answer_4,
            "phase_2_answer_5": self.phase_2_answer_5,
            "phase_2_answer_6": self.phase_2_answer_6,
        }
