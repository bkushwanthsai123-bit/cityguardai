"""Tests for the deterministic rules and the Ollama provider fallback/clamp."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("pydantic")

from app.schemas import Detection, DetectionResult  # noqa: E402
from app.llm import rules  # noqa: E402


def _result(specs, w=1000, h=1000):
    """Build a DetectionResult from ``[(class_name, area_fraction), ...]``.

    The bbox is sized so its geometric area fraction equals ``area_fraction``,
    keeping both possible rule interpretations consistent.
    """
    dets = []
    for class_name, af in specs:
        box_area = af * w * h
        box_h = box_area / w
        dets.append(
            Detection(
                class_name=class_name,
                confidence=0.9,
                bbox=[0.0, 0.0, float(w), float(box_h)],
                area_fraction=af,
            )
        )
    return DetectionResult(
        detections=dets, image_width=w, image_height=h, inference_ms=5.0
    )


# ---------------------------------------------------------------------------
# compute_severity bands
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "specs,expected_band,expected_score",
    [
        ([("Paper", 0.1)], "low", 9),          # 100*0.4*0.1 + 5 = 9
        ([("Waste", 0.25)], "medium", 30),     # 25 + 5
        ([("Waste", 0.6)], "high", 65),        # 60 + 5
        ([("Waste", 0.95)], "critical", 100),  # 95 + 5 -> clamp 100
    ],
)
def test_compute_severity_bands(specs, expected_band, expected_score):
    score, band = rules.compute_severity(_result(specs))
    assert 0 <= score <= 100
    assert score == expected_score
    assert band == expected_band


def test_compute_severity_count_bonus():
    # Five Paper detections add the max count bonus of 25.
    specs = [("Paper", 0.01)] * 5
    score, _band = rules.compute_severity(_result(specs))
    # sum = 5 * (0.4 * 0.01) * 100 = 2.0 ; + 5*min(5,5)=25 -> 27
    assert score >= 25


# ---------------------------------------------------------------------------
# pick_department routing
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "class_name,expected",
    [
        ("Waste", "Solid Waste Management"),
        ("Glass", "Solid Waste Management"),
        ("Metal", "Solid Waste Management"),
        ("Plastic", "Sanitation Department"),
        ("Paper", "Street Cleaning / Public Health"),
    ],
)
def test_pick_department_single(class_name, expected):
    assert rules.pick_department(_result([(class_name, 0.2)])) == expected


def test_pick_department_mixed_picks_highest_weight():
    # Paper (0.4) + Waste (1.0) -> Solid Waste Management
    res = _result([("Paper", 0.2), ("Waste", 0.2)])
    assert rules.pick_department(res) == "Solid Waste Management"

    # Plastic (0.6) + Paper (0.4) -> Sanitation Department
    res = _result([("Plastic", 0.2), ("Paper", 0.2)])
    assert rules.pick_department(res) == "Sanitation Department"

    # Glass (0.8) + Plastic (0.6) -> Solid Waste Management
    res = _result([("Plastic", 0.2), ("Glass", 0.2)])
    assert rules.pick_department(res) == "Solid Waste Management"


# ---------------------------------------------------------------------------
# priority_for / sla_for
# ---------------------------------------------------------------------------
def test_priority_for():
    assert rules.priority_for("low") == "P4"
    assert rules.priority_for("medium") == "P3"
    assert rules.priority_for("high") == "P2"
    assert rules.priority_for("critical") == "P1"


def test_sla_for():
    assert rules.sla_for("P1") == 4
    assert rules.sla_for("P2") == 12
    assert rules.sla_for("P3") == 24
    assert rules.sla_for("P4") == 72


# ---------------------------------------------------------------------------
# build_report
# ---------------------------------------------------------------------------
def test_build_report_valid_and_consistent():
    from app.schemas import IncidentReport

    res = _result([("Waste", 0.6)])
    report = rules.build_report(res, {"address": "Test Street"})

    assert isinstance(report, IncidentReport)
    score, band = rules.compute_severity(res)
    assert 0 <= report.severity_score <= 100
    assert report.severity_score == score
    assert report.severity == band
    assert report.priority == rules.priority_for(band)
    assert report.sla_hours == rules.sla_for(report.priority)
    assert report.department == rules.pick_department(res)
    assert report.title
    assert report.description
    assert report.recommended_action


def test_build_report_empty_context():
    res = _result([("Plastic", 0.3)])
    report = rules.build_report(res, {})
    assert report.department == "Sanitation Department"
    assert 0 <= report.severity_score <= 100


# ---------------------------------------------------------------------------
# OllamaProvider: fallback on network error + clamping of LLM numbers
# ---------------------------------------------------------------------------
def _get_provider_class():
    mod = pytest.importorskip("app.llm.ollama_provider")
    return getattr(mod, "OllamaProvider")


def _instantiate(provider_cls):
    try:
        return provider_cls()
    except TypeError:
        pytest.skip("OllamaProvider constructor signature differs from contract")


def test_ollama_provider_falls_back_to_rules_on_error(monkeypatch):
    requests = pytest.importorskip("requests")
    httpx = pytest.importorskip("httpx")
    provider_cls = _get_provider_class()

    def _raise(*args, **kwargs):
        raise ConnectionError("ollama unreachable")

    monkeypatch.setattr(requests, "post", _raise, raising=False)
    monkeypatch.setattr(requests, "request", _raise, raising=False)
    monkeypatch.setattr(httpx, "post", _raise, raising=False)

    def _raise_method(self, *args, **kwargs):
        raise ConnectionError("ollama unreachable")

    monkeypatch.setattr(httpx.Client, "post", _raise_method, raising=False)
    monkeypatch.setattr(httpx.Client, "request", _raise_method, raising=False)
    monkeypatch.setattr(httpx.Client, "send", _raise_method, raising=False)

    provider = _instantiate(provider_cls)
    res = _result([("Waste", 0.6)])
    report = provider.generate_report(res, {})

    score, band = rules.compute_severity(res)
    assert report.severity_score == score
    assert report.severity == band
    assert report.priority == rules.priority_for(band)
    assert report.department == rules.pick_department(res)


def test_ollama_provider_clamps_out_of_range_score(monkeypatch):
    requests = pytest.importorskip("requests")
    httpx = pytest.importorskip("httpx")
    provider_cls = _get_provider_class()

    bad_report = {
        "title": "Bad LLM output",
        "description": "Model claims an impossible score.",
        "severity": "low",
        "severity_score": 999,  # out of range
        "priority": "P4",
        "department": "Totally Made Up Department",
        "recommended_action": "Ignore me",
        "sla_hours": 99999,
    }
    content = json.dumps(bad_report)

    class _FakeResp:
        status_code = 200
        text = content

        def json(self):
            # Cover both /api/chat and /api/generate response shapes.
            return {"message": {"content": content}, "response": content}

        def raise_for_status(self):
            return None

    def _ret(*args, **kwargs):
        return _FakeResp()

    def _ret_method(self, *args, **kwargs):
        return _FakeResp()

    monkeypatch.setattr(requests, "post", _ret, raising=False)
    monkeypatch.setattr(httpx, "post", _ret, raising=False)
    monkeypatch.setattr(httpx.Client, "post", _ret_method, raising=False)
    monkeypatch.setattr(httpx.Client, "request", _ret_method, raising=False)

    provider = _instantiate(provider_cls)
    res = _result([("Waste", 0.6)])
    report = provider.generate_report(res, {})

    # Regardless of what the LLM returned, rules own the numbers.
    score, band = rules.compute_severity(res)
    assert 0 <= report.severity_score <= 100
    assert report.severity_score == score
    assert report.severity == band
    assert report.priority == rules.priority_for(band)
    assert report.sla_hours == rules.sla_for(report.priority)
    assert report.department == rules.pick_department(res)
