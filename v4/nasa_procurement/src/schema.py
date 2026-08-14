"""Pydantic models for the raw -> clean -> enriched transaction pipeline,
plus agent I/O and refresh-manifest schemas.

Field mapping (source -> internal) is documented in README.md under
"Data model". All fields below are Optional unless USAspending guarantees
them on every prime-contract transaction, because real government data is
frequently missing individual attributes and the pipeline must never crash
on a missing field -- it should flag it instead (see `data_quality_flags`).
"""
from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ObligationDirection(str, Enum):
    OBLIGATION = "OBLIGATION"
    DEOBLIGATION = "DEOBLIGATION"
    ZERO_DOLLAR_ACTION = "ZERO_DOLLAR_ACTION"


class ReviewStatus(str, Enum):
    OK = "OK"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class ProcessingMode(str, Enum):
    LIVE_AGENT = "LIVE_AGENT"
    CACHED_AGENT = "CACHED_AGENT"
    DETERMINISTIC_FALLBACK = "DETERMINISTIC_FALLBACK"


class CleanTransaction(BaseModel):
    # --- identity ---
    transaction_id: str
    award_id_piid: str
    parent_award_id: Optional[str] = None
    generated_award_id: Optional[str] = None
    modification_number: Optional[str] = None

    # --- action ---
    action_date: dt.date
    fiscal_year: int
    action_type_code: Optional[str] = None
    action_type_description: Optional[str] = None
    transaction_description: Optional[str] = None

    # --- amount (source, signed, pre-derivation) ---
    transaction_obligated_amount: float

    # --- recipient ---
    recipient_name_raw: str
    recipient_uei: Optional[str] = None
    recipient_duns: Optional[str] = None
    parent_recipient_name: Optional[str] = None
    parent_recipient_uei: Optional[str] = None
    parent_recipient_duns: Optional[str] = None
    recipient_location_city: Optional[str] = None
    recipient_location_state: Optional[str] = None
    recipient_location_country: Optional[str] = None

    # --- agency ---
    awarding_agency: Optional[str] = None
    awarding_subagency: Optional[str] = None
    awarding_office: Optional[str] = None
    funding_agency: Optional[str] = None
    funding_subagency: Optional[str] = None

    # --- award classification ---
    award_type_code: Optional[str] = None
    award_type_description: Optional[str] = None
    psc_code: Optional[str] = None
    psc_description: Optional[str] = None
    naics_code: Optional[str] = None
    naics_description: Optional[str] = None

    # --- performance ---
    period_of_performance_start: Optional[dt.date] = None
    period_of_performance_current_end: Optional[dt.date] = None
    place_of_performance_city: Optional[str] = None
    place_of_performance_state: Optional[str] = None
    place_of_performance_country: Optional[str] = None

    # --- award-level context (broadcast from latest award state; see README) ---
    current_award_amount: Optional[float] = None
    potential_award_amount: Optional[float] = None
    extent_competed: Optional[str] = None
    extent_competed_description: Optional[str] = None
    contract_pricing_type: Optional[str] = None
    contract_pricing_type_description: Optional[str] = None
    set_aside_type: Optional[str] = None
    set_aside_type_description: Optional[str] = None
    number_of_offers_received: Optional[int] = None

    award_detail_available: bool = False


class EnrichedTransaction(CleanTransaction):
    # --- signed obligation logic ---
    transaction_obligation_signed: float
    transaction_obligation_absolute: float
    obligation_direction: ObligationDirection
    cumulative_award_obligation: float

    # --- supplier resolution ---
    normalized_supplier: str
    supplier_resolution_confidence: float
    supplier_resolution_evidence: str

    # --- classification ---
    ai_spend_category: str
    ai_spend_subcategory: str
    classification_confidence: float
    classification_evidence: str

    review_status: ReviewStatus = ReviewStatus.OK
    opportunity_flags: list[str] = Field(default_factory=list)
    data_quality_flags: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Agent I/O schemas
# --------------------------------------------------------------------------

class SupplierResolutionResult(BaseModel):
    raw_name: str
    canonical_supplier: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str
    needs_review: bool = False


class ClassificationResult(BaseModel):
    category: str
    subcategory: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str
    needs_review: bool = False


class InsightFinding(BaseModel):
    title: str
    description: str
    supporting_metrics: list[str]
    affected_entities: list[str] = Field(default_factory=list)
    confidence_language: str = "potential opportunity — warrants review"


class InsightsResult(BaseModel):
    findings: list[InsightFinding]


# --------------------------------------------------------------------------
# Refresh manifest
# --------------------------------------------------------------------------

class RefreshManifest(BaseModel):
    run_id: str
    retrieved_at: str
    source: str
    query_parameters: dict
    processing_mode: ProcessingMode
    row_counts: dict
    validation_results: dict
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
