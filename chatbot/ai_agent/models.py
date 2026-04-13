"""Pydantic models for agent I/O and AI provider configuration."""

from __future__ import annotations

from enum import StrEnum

# ---------------------------------------------------------------------------
# AI model enums
# ---------------------------------------------------------------------------


class GoogleModel(StrEnum):
    Gemini_Flash_Latest = "google-gla:gemini-flash-latest"
    Gemini_Flash_Lite_Latest = "google-gla:gemini-flash-lite-latest"
    Gemini_Pro_Latest = "google-gla:gemini-pro-latest"
    Gemini_3_Pro_Preview = "google-gla:gemini-3-pro-preview"
    Gemini_3_Flash_Preview = "google-gla:gemini-3-flash-preview"
    Gemini_3_1_Pro_Preview = "google-gla:gemini-3.1-pro-preview"
    Gemini_3_1_Pro_Preview_Custom_Tools = (
        "google-gla:gemini-3.1-pro-preview-customtools"
    )
    Gemini_3_1_Flash_Lite_Preview = "google-gla:gemini-3.1-flash-lite-preview"
