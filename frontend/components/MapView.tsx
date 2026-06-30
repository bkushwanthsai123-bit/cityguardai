"use client";

import { useEffect, useState } from "react";
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Popup,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";
import {
  Incident,
  Severity,
  getIncidents,
  SEVERITY_COLORS,
} from "@/lib/api";
import { Spinner } from "@/components/ui/Spinner";

const CENTER: [number, number] = [12.9716, 77.5946];
const SEV_ORDER: Severity[] = ["low", "medium", "high", "critical"];

export default function MapView() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getIncidents()
      .then((inc) => {
        if (active) setIncidents(inc.filter((i) => i.lat != null && i.lon != null));
      })
      .catch((e) => {
        if (active) setError(e instanceof Error ? e.message : "Failed to load");
      })
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="relative h-full w-full overflow-hidden rounded-xl border border-[#1e222b]">
      <MapContainer
        center={CENTER}
        zoom={12}
        scrollWheelZoom
        style={{ height: "100%", width: "100%" }}
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        />
        {incidents.map((inc) => (
          <CircleMarker
            key={inc.id}
            center={[inc.lat as number, inc.lon as number]}
            radius={8}
            pathOptions={{
              color: SEVERITY_COLORS[inc.severity],
              fillColor: SEVERITY_COLORS[inc.severity],
              fillOpacity: 0.7,
              weight: 2,
            }}
          >
            <Popup>
              <div style={{ minWidth: 180 }}>
                <p style={{ fontWeight: 600, marginBottom: 4 }}>{inc.title}</p>
                <p style={{ fontSize: 12, color: "#8b909c" }}>
                  Severity:{" "}
                  <span style={{ color: SEVERITY_COLORS[inc.severity] }}>
                    {inc.severity}
                  </span>
                </p>
                <p style={{ fontSize: 12, color: "#8b909c" }}>
                  Department: {inc.department}
                </p>
                <p style={{ fontSize: 12, color: "#8b909c" }}>
                  Status: {inc.status}
                </p>
                {inc.address && (
                  <p style={{ fontSize: 12, color: "#8b909c" }}>
                    {inc.address}
                  </p>
                )}
              </div>
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>

      {/* Legend */}
      <div className="absolute bottom-4 right-4 z-[1000] rounded-lg border border-[#1e222b] bg-[#111317]/95 p-3 text-xs shadow-lg">
        <p className="mb-2 font-medium text-[#e7e9ee]">Severity</p>
        <ul className="space-y-1">
          {SEV_ORDER.map((s) => (
            <li key={s} className="flex items-center gap-2 text-[#8b909c]">
              <span
                className="inline-block h-2.5 w-2.5 rounded-full"
                style={{ background: SEVERITY_COLORS[s] }}
              />
              <span className="capitalize">{s}</span>
            </li>
          ))}
        </ul>
      </div>

      {loading && (
        <div className="absolute left-4 top-4 z-[1000] flex items-center gap-2 rounded-lg border border-[#1e222b] bg-[#111317]/95 px-3 py-2 text-xs text-[#8b909c]">
          <Spinner size={14} /> Loading incidents...
        </div>
      )}
      {error && (
        <div className="absolute left-4 top-4 z-[1000] rounded-lg border border-[#ef444433] bg-[#111317]/95 px-3 py-2 text-xs text-[#fca5a5]">
          {error}
        </div>
      )}
    </div>
  );
}
