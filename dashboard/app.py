"""Streamlit dashboard for the Smart City illegal garbage dumping detector.

Talks to the FastAPI backend over HTTP. The base URL is read from the
``API_URL`` environment variable (default ``http://localhost:8000``).

Run with:  streamlit run dashboard/app.py
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

API_URL = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT = 30

SEVERITY_OPTIONS = ["low", "medium", "high", "critical"]
STATUS_OPTIONS = ["open", "in_progress", "resolved"]
PRIORITY_OPTIONS = ["P1", "P2", "P3", "P4"]
DEPARTMENT_OPTIONS = [
    "Solid Waste Management",
    "Sanitation Department",
    "Street Cleaning / Public Health",
]

# Marker / badge colors keyed by severity band.
SEVERITY_COLORS = {
    "low": "#2e7d32",
    "medium": "#f9a825",
    "high": "#ef6c00",
    "critical": "#c62828",
}


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
class ApiError(Exception):
    """Raised when the backend is unreachable or returns an error status."""


def _url(path: str) -> str:
    return API_URL + path


def api_get(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    try:
        resp = requests.get(_url(path), params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        raise ApiError(str(exc)) from exc


def api_patch(path: str, payload: Dict[str, Any]) -> Any:
    try:
        resp = requests.patch(_url(path), json=payload, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        raise ApiError(str(exc)) from exc


def api_delete(path: str) -> Any:
    try:
        resp = requests.delete(_url(path), timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        raise ApiError(str(exc)) from exc


def api_detect(
    file_name: str,
    file_bytes: bytes,
    content_type: str,
    lat: Optional[float],
    lon: Optional[float],
    address: Optional[str],
) -> Any:
    files = {"file": (file_name, file_bytes, content_type or "application/octet-stream")}
    data: Dict[str, Any] = {}
    if lat is not None:
        data["lat"] = lat
    if lon is not None:
        data["lon"] = lon
    if address:
        data["address"] = address
    try:
        resp = requests.post(
            _url("/detect"), files=files, data=data, timeout=120
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        raise ApiError(str(exc)) from exc


def api_get_annotated(incident_id: Any) -> Optional[bytes]:
    """Fetch an incident's stored annotated media (boxes drawn), a .jpg or .gif.

    Generated once at incident creation, so no second inference pass is needed.
    """
    if incident_id is None:
        return None
    try:
        resp = requests.get(_url(f"/incidents/{incident_id}/annotated"), timeout=60)
        resp.raise_for_status()
        return resp.content
    except requests.RequestException:
        return None


def api_detect_video(
    file_name: str,
    file_bytes: bytes,
    content_type: str,
    lat: Optional[float],
    lon: Optional[float],
    address: Optional[str],
) -> Any:
    """Run video detection: samples frames, stores one aggregated incident."""
    files = {"file": (file_name, file_bytes, content_type or "application/octet-stream")}
    data: Dict[str, Any] = {}
    if lat is not None:
        data["lat"] = lat
    if lon is not None:
        data["lon"] = lon
    if address:
        data["address"] = address
    try:
        resp = requests.post(_url("/detect/video"), files=files, data=data, timeout=300)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        raise ApiError(str(exc)) from exc


def check_health() -> Optional[Dict[str, Any]]:
    try:
        return api_get("/health")
    except ApiError:
        return None


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------
def severity_badge(severity: str) -> str:
    color = SEVERITY_COLORS.get(severity, "#555555")
    return (
        "<span style='background-color:" + color + ";color:white;"
        "padding:3px 10px;border-radius:6px;font-weight:600;'>"
        + str(severity).upper()
        + "</span>"
    )


def render_incident_report(incident: Dict[str, Any]) -> None:
    cols = st.columns([1, 1, 1])
    with cols[0]:
        st.markdown("**Severity**", unsafe_allow_html=True)
        st.markdown(severity_badge(incident.get("severity", "")), unsafe_allow_html=True)
        st.caption("Score: " + str(incident.get("severity_score", "-")))
    with cols[1]:
        st.metric("Priority", incident.get("priority", "-"))
        st.caption("SLA: " + str(incident.get("sla_hours", "-")) + "h")
    with cols[2]:
        st.metric("Department", "")
        st.write(incident.get("department", "-"))

    st.subheader(incident.get("title", "Incident"))
    st.write(incident.get("description", ""))
    st.markdown("**Recommended action:** " + str(incident.get("recommended_action", "-")))
    st.caption(
        "Detections: "
        + str(incident.get("num_detections", 0))
        + " | Classes: "
        + ", ".join(incident.get("classes", []) or [])
    )


def sidebar_filters() -> Dict[str, Any]:
    st.sidebar.header("Filters")
    department = st.sidebar.selectbox("Department", ["All"] + DEPARTMENT_OPTIONS)
    severity = st.sidebar.selectbox("Severity", ["All"] + SEVERITY_OPTIONS)
    status = st.sidebar.selectbox("Status", ["All"] + STATUS_OPTIONS)
    priority = st.sidebar.selectbox("Priority", ["All"] + PRIORITY_OPTIONS)

    default_from = date.today() - timedelta(days=30)
    date_range = st.sidebar.date_input(
        "Date range", value=(default_from, date.today())
    )

    params: Dict[str, Any] = {"limit": 500, "offset": 0}
    if department != "All":
        params["department"] = department
    if severity != "All":
        params["severity"] = severity
    if status != "All":
        params["status"] = status
    if priority != "All":
        params["priority"] = priority
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        params["date_from"] = date_range[0].isoformat()
        params["date_to"] = date_range[1].isoformat()
    return params


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
def tab_overview(incidents: List[Dict[str, Any]]) -> None:
    """At-a-glance summary: KPIs, breakdowns, top hotspot, trend, recents."""
    st.subheader("Overview")
    try:
        summary = api_get("/analytics/summary")
    except ApiError as exc:
        st.error("Could not load overview: " + str(exc))
        return

    by_status = summary.get("by_status", {}) or {}
    by_severity = summary.get("by_severity", {}) or {}
    by_priority = summary.get("by_priority", {}) or {}
    high = (by_severity.get("high", 0) or 0) + (by_severity.get("critical", 0) or 0)

    k = st.columns(5)
    k[0].metric("Total incidents", summary.get("total", 0))
    k[1].metric("Open", by_status.get("open", 0))
    k[2].metric("In progress", by_status.get("in_progress", 0))
    k[3].metric("Resolved", by_status.get("resolved", 0))
    k[4].metric("High / Critical", high)

    st.markdown("---")
    left, right = st.columns([2, 1])
    with left:
        b = st.columns(2)
        with b[0]:
            st.caption("By severity")
            st.bar_chart(by_severity)
        with b[1]:
            st.caption("By priority")
            st.bar_chart(by_priority)
        trend = summary.get("trend", []) or []
        if trend:
            st.caption("Trend (last 30 days)")
            st.line_chart({str(p.get("date")): p.get("count", 0) for p in trend})
    with right:
        st.caption("Top hotspot")
        try:
            hotspots = api_get("/analytics/hotspots")
        except ApiError:
            hotspots = []
        if hotspots:
            top = hotspots[0]
            label = top.get("address") or top.get("area") or (
                f"{top.get('lat')}, {top.get('lon')}"
                if top.get("lat") is not None else "Unknown location"
            )
            count = top.get("count") or top.get("incident_count") or top.get("num_incidents")
            st.metric(str(label), count if count is not None else "-")
        else:
            st.info("No hotspots yet.")

        st.caption("By department")
        st.bar_chart(summary.get("by_department", {}) or {})

    st.markdown("---")
    st.caption("Recent incidents")
    recent = incidents[:5]
    if not recent:
        st.info("No incidents match the current filters.")
        return
    for inc in recent:
        c = st.columns([1, 4, 2, 2])
        c[0].markdown(severity_badge(inc.get("severity", "")), unsafe_allow_html=True)
        c[1].write("**#" + str(inc.get("id")) + "** " + str(inc.get("title", "")))
        c[2].caption(str(inc.get("priority", "")) + " | " + str(inc.get("status", "")))
        c[3].caption(str(inc.get("created_at", ""))[:19].replace("T", " "))


def tab_incidents(incidents: List[Dict[str, Any]]) -> None:
    st.subheader("Incidents")
    if not incidents:
        st.info("No incidents match the current filters.")
        return

    table_rows = [
        {
            "id": inc.get("id"),
            "created_at": inc.get("created_at"),
            "severity": inc.get("severity"),
            "priority": inc.get("priority"),
            "department": inc.get("department"),
            "status": inc.get("status"),
            "score": inc.get("severity_score"),
        }
        for inc in incidents
    ]
    st.dataframe(table_rows, use_container_width=True)

    ids = [inc.get("id") for inc in incidents]
    selected = st.selectbox("Inspect / update incident", ["-"] + ids)
    if selected != "-":
        incident = next((i for i in incidents if i.get("id") == selected), None)
        if incident:
            render_incident_report(incident)
            new_status = st.selectbox(
                "Update status",
                STATUS_OPTIONS,
                index=STATUS_OPTIONS.index(incident.get("status", "open"))
                if incident.get("status") in STATUS_OPTIONS
                else 0,
            )
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("Save status"):
                    try:
                        api_patch("/incidents/" + str(selected), {"status": new_status})
                        st.success("Status updated.")
                    except ApiError as exc:
                        st.error("Update failed: " + str(exc))
            with col_b:
                if st.button("Delete incident"):
                    try:
                        api_delete("/incidents/" + str(selected))
                        st.success("Incident deleted.")
                    except ApiError as exc:
                        st.error("Delete failed: " + str(exc))


VIDEO_EXTS = ("mp4", "mov", "webm", "avi", "mkv")


def _is_video(uploaded) -> bool:
    """Whether the uploaded file is a video (by extension or MIME type)."""
    name = getattr(uploaded, "name", "") or ""
    ctype = getattr(uploaded, "type", "") or ""
    return name.lower().rsplit(".", 1)[-1] in VIDEO_EXTS or ctype.startswith("video/")


def tab_upload_detect() -> None:
    st.subheader("Upload & Detect")
    uploaded = st.file_uploader(
        "Upload an image or video",
        type=["jpg", "jpeg", "png", "bmp", "webp", *VIDEO_EXTS],
    )
    col1, col2 = st.columns(2)
    with col1:
        lat = st.number_input("Latitude", value=0.0, format="%.6f")
        lon = st.number_input("Longitude", value=0.0, format="%.6f")
    with col2:
        address = st.text_input("Address (optional)")

    is_video = uploaded is not None and _is_video(uploaded)
    if uploaded is not None:
        if is_video:
            st.video(uploaded)
            st.caption("Long videos are frame-sampled and capped for speed.")
        else:
            st.image(uploaded, caption="Uploaded image", use_column_width=True)

    if st.button("Run detection", disabled=uploaded is None):
        if uploaded is None:
            st.warning("Please upload an image or video first.")
            return
        content_type = getattr(uploaded, "type", "application/octet-stream")
        spin = "Analysing video frames..." if is_video else "Detecting and generating report..."
        with st.spinner(spin):
            try:
                if is_video:
                    incident = api_detect_video(
                        uploaded.name, uploaded.getvalue(), content_type,
                        lat if lat != 0.0 else None,
                        lon if lon != 0.0 else None,
                        address or None,
                    )
                else:
                    incident = api_detect(
                        uploaded.name, uploaded.getvalue(), content_type,
                        lat if lat != 0.0 else None,
                        lon if lon != 0.0 else None,
                        address or None,
                    )
            except ApiError as exc:
                st.error("Detection failed: " + str(exc))
                return
        st.success("Incident created (id " + str(incident.get("id")) + ").")
        # The annotated media (boxes drawn) is generated once when the incident
        # is created; fetch the stored file instead of re-running detection.
        annotated = api_get_annotated(incident.get("id"))
        if annotated:
            caption = "Detections (animated)" if is_video else "Detections"
            st.image(annotated, caption=caption, use_column_width=True)
        render_incident_report(incident)


def tab_map(incidents: List[Dict[str, Any]]) -> None:
    st.subheader("Map")
    geo = [
        inc
        for inc in incidents
        if inc.get("lat") is not None and inc.get("lon") is not None
    ]
    if not geo:
        st.info("No geolocated incidents to plot.")
        return

    try:
        import folium
        from streamlit_folium import st_folium

        center_lat = sum(i["lat"] for i in geo) / len(geo)
        center_lon = sum(i["lon"] for i in geo) / len(geo)
        # Dark basemap to match the dashboard's dark theme.
        fmap = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=12,
            tiles="CartoDB dark_matter",
        )
        for inc in geo:
            color = SEVERITY_COLORS.get(inc.get("severity", ""), "#555555")
            popup = (
                "ID "
                + str(inc.get("id"))
                + "<br>"
                + str(inc.get("severity", ""))
                + " ("
                + str(inc.get("priority", ""))
                + ")<br>"
                + str(inc.get("department", ""))
                + "<br>Status: "
                + str(inc.get("status", ""))
            )
            folium.CircleMarker(
                location=[inc["lat"], inc["lon"]],
                radius=8,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.8,
                popup=folium.Popup(popup, max_width=250),
            ).add_to(fmap)
        st_folium(fmap, width=900, height=520)
    except ImportError:
        st.caption("folium not installed; showing basic map.")
        st.map(
            [{"lat": i["lat"], "lon": i["lon"]} for i in geo],
        )


def tab_analytics() -> None:
    st.subheader("Analytics")
    try:
        summary = api_get("/analytics/summary")
    except ApiError as exc:
        st.error("Could not load analytics: " + str(exc))
        return

    cols = st.columns(4)
    cols[0].metric("Total incidents", summary.get("total", 0))
    by_status = summary.get("by_status", {}) or {}
    cols[1].metric("Open", by_status.get("open", 0))
    cols[2].metric("In progress", by_status.get("in_progress", 0))
    cols[3].metric("Resolved", by_status.get("resolved", 0))

    chart_cols = st.columns(3)
    with chart_cols[0]:
        st.caption("By department")
        st.bar_chart(summary.get("by_department", {}) or {})
    with chart_cols[1]:
        st.caption("By severity")
        st.bar_chart(summary.get("by_severity", {}) or {})
    with chart_cols[2]:
        st.caption("By status")
        st.bar_chart(by_status)

    trend = summary.get("trend", []) or []
    if trend:
        st.caption("Trend")
        trend_data = {
            str(point.get("date")): point.get("count", 0) for point in trend
        }
        st.line_chart(trend_data)

    st.markdown("---")
    st.caption("Hotspots")
    try:
        hotspots = api_get("/analytics/hotspots")
        if hotspots:
            st.dataframe(hotspots, use_container_width=True)
        else:
            st.info("No hotspots yet.")
    except ApiError as exc:
        st.error("Could not load hotspots: " + str(exc))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(page_title="Smart City Garbage Detection", layout="wide")
    st.title("Smart City - Illegal Garbage Dumping Detection")
    st.caption("API: " + API_URL)

    health = check_health()
    if health is None:
        st.error(
            "Cannot reach the backend API at "
            + API_URL
            + ". Start the API (uvicorn app.main:app) or set the API_URL "
            "environment variable."
        )
        st.stop()
    else:
        st.success(
            "API online | model_loaded="
            + str(health.get("model_loaded"))
            + " db_ok="
            + str(health.get("db_ok"))
            + " ollama_ok="
            + str(health.get("ollama_ok"))
        )

    params = sidebar_filters()
    try:
        incidents = api_get("/incidents", params=params)
    except ApiError as exc:
        st.error("Could not load incidents: " + str(exc))
        incidents = []

    tabs = st.tabs(["Overview", "Incidents", "Upload & Detect", "Map", "Analytics"])
    with tabs[0]:
        tab_overview(incidents)
    with tabs[1]:
        tab_incidents(incidents)
    with tabs[2]:
        tab_upload_detect()
    with tabs[3]:
        tab_map(incidents)
    with tabs[4]:
        tab_analytics()


if __name__ == "__main__":
    main()
