"use client";

import { useRef, useState } from "react";
import { ImageIcon, Sparkles, CheckCircle2, Cpu } from "lucide-react";
import { Incident, detect, imageUrl } from "@/lib/api";
import { PageHeader, SectionTitle } from "@/components/ui/SectionTitle";
import { Card } from "@/components/ui/Card";
import { SeverityBadge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";

const LOCATIONS = [
  { name: "MG Road", lat: 12.9758, lon: 77.6045 },
  { name: "Koramangala", lat: 12.9352, lon: 77.6245 },
  { name: "Whitefield", lat: 12.9698, lon: 77.75 },
  { name: "Indiranagar", lat: 12.9719, lon: 77.6412 },
  { name: "Electronic City", lat: 12.8452, lon: 77.6602 },
];

const PIPELINE = [
  {
    n: 1,
    color: "#3b82f6",
    name: "Image Preprocessing",
    time: "~3ms",
    desc: "Resize to 640x640, normalize, mosaic augmentation.",
  },
  {
    n: 2,
    color: "#a855f7",
    name: "YOLOv8 Inference",
    time: "~25ms",
    desc: "Forward pass through the detector; 5 waste classes.",
  },
  {
    n: 3,
    color: "#f97316",
    name: "Non-Max Suppression",
    time: "~2ms",
    desc: "IoU=0.45 removes duplicate boxes; conf=0.25.",
  },
  {
    n: 4,
    color: "#22c55e",
    name: "Llama 3.2 Report",
    time: "~800ms",
    desc: "Structured JSON via local Ollama: severity, priority, dept, action.",
  },
  {
    n: 5,
    color: "#06b6d4",
    name: "Database Persistence",
    time: "~30ms",
    desc: "Incident + boxes + LLM report saved to SQLite.",
  },
];

const MODEL_CARD: { k: string; v: string }[] = [
  { k: "Architecture", v: "YOLOv8m-seg" },
  { k: "Input", v: "640x640" },
  { k: "Classes", v: "5" },
  { k: "Class names", v: "Glass, Metal, Paper, Plastic, Waste" },
  { k: "Params", v: "~11.2M" },
  { k: "Conf threshold", v: "0.25" },
  { k: "LLM", v: "Llama 3.2 1B (Ollama)" },
  { k: "mAP@0.5", v: "~0.43 (pretrained; retrain for higher)" },
];

export default function DetectPage() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [lat, setLat] = useState<string>("");
  const [lon, setLon] = useState<string>("");
  const [address, setAddress] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Incident | null>(null);

  function onFile(f: File | null) {
    setFile(f);
    setResult(null);
    setError(null);
    if (f) {
      setPreview(URL.createObjectURL(f));
    } else {
      setPreview(null);
    }
  }

  function onLocation(name: string) {
    const loc = LOCATIONS.find((l) => l.name === name);
    if (loc) {
      setLat(String(loc.lat));
      setLon(String(loc.lon));
      setAddress(`${loc.name}, Bengaluru`);
    }
  }

  async function run() {
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const inc = await detect(file, {
        lat: lat ? Number(lat) : null,
        lon: lon ? Number(lon) : null,
        address: address || null,
      });
      setResult(inc);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Detection failed");
    } finally {
      setLoading(false);
    }
  }

  const resultImg = result ? imageUrl(result.image_path) : null;

  return (
    <div>
      <PageHeader
        title="Detect Illegal Dumping"
        subtitle="Upload a street image to run the full YOLOv8 + Llama 3.2 detection pipeline."
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* LEFT */}
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <SectionTitle title="Detect Illegal Dumping" />

            {/* Dropzone */}
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              className="flex w-full flex-col items-center justify-center rounded-lg border border-dashed border-[#2a3040] bg-[#0c0e12] px-6 py-10 text-center transition-colors hover:border-[#3b82f6] hover:bg-[#0e1117]"
            >
              {preview ? (
                <span className="relative block h-44 w-full max-w-sm overflow-hidden rounded-lg border border-[#1e222b]">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={preview}
                    alt="preview"
                    className="h-full w-full object-cover"
                  />
                </span>
              ) : (
                <span className="flex h-12 w-12 items-center justify-center rounded-full bg-[#15181e] text-[#8b909c]">
                  <ImageIcon className="h-6 w-6" />
                </span>
              )}
              <span className="mt-3 text-sm font-medium text-[#e7e9ee]">
                {file ? file.name : "Click to upload image"}
              </span>
              <span className="mt-1 text-xs text-[#8b909c]">
                JPG, PNG, WEBP up to 10MB
              </span>
            </button>
            <input
              ref={fileRef}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              className="hidden"
              onChange={(e) => onFile(e.target.files?.[0] ?? null)}
            />

            {/* Location preset */}
            <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Quick Location (Bengaluru)">
                <select
                  defaultValue=""
                  onChange={(e) => onLocation(e.target.value)}
                  className="input"
                >
                  <option value="" disabled>
                    — Select a location —
                  </option>
                  {LOCATIONS.map((l) => (
                    <option key={l.name} value={l.name}>
                      {l.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Address (optional)">
                <input
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  placeholder="e.g. 14th Main, Indiranagar"
                  className="input"
                />
              </Field>
              <Field label="Latitude">
                <input
                  type="number"
                  step="any"
                  value={lat}
                  onChange={(e) => setLat(e.target.value)}
                  placeholder="12.9716"
                  className="input"
                />
              </Field>
              <Field label="Longitude">
                <input
                  type="number"
                  step="any"
                  value={lon}
                  onChange={(e) => setLon(e.target.value)}
                  placeholder="77.5946"
                  className="input"
                />
              </Field>
            </div>

            <button
              type="button"
              disabled={!file || loading}
              onClick={run}
              className="brand-gradient mt-5 flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium text-white shadow-lg shadow-blue-500/20 transition-opacity disabled:cursor-not-allowed disabled:opacity-40"
            >
              {loading ? (
                <>
                  <Spinner size={16} /> Running pipeline...
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" /> Run detection
                </>
              )}
            </button>

            {error && (
              <p className="mt-3 rounded-lg border border-[#ef444433] bg-[#ef44440d] px-3 py-2 text-sm text-[#fca5a5]">
                {error}
              </p>
            )}
          </Card>

          {/* RESULT */}
          {result && (
            <Card>
              <SectionTitle title="Incident Report" subtitle={result.title} />
              {result.num_detections === 0 ? (
                <div className="flex flex-col items-center rounded-lg border border-[#1e222b] bg-[#0c0e12] px-6 py-10 text-center">
                  <CheckCircle2 className="h-8 w-8 text-[#22c55e]" />
                  <p className="mt-2 text-sm font-medium text-[#e7e9ee]">
                    No garbage detected
                  </p>
                  <p className="mt-1 text-sm text-[#8b909c]">
                    The image looks clean. No incident action required.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                  {resultImg && (
                    <div className="overflow-hidden rounded-lg border border-[#1e222b]">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={resultImg}
                        alt={result.title}
                        className="h-full max-h-72 w-full object-cover"
                      />
                    </div>
                  )}
                  <div className="space-y-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <SeverityBadge severity={result.severity} />
                      <span className="text-xs text-[#8b909c]">
                        score {result.severity_score.toFixed(2)}
                      </span>
                      <span className="rounded-full border border-[#1e222b] bg-[#0c0e12] px-2.5 py-0.5 text-xs font-medium text-[#e7e9ee]">
                        {result.priority}
                      </span>
                    </div>
                    <KV k="Department" v={result.department} />
                    <KV k="SLA" v={`${result.sla_hours} hours`} />
                    <div>
                      <p className="text-xs uppercase tracking-wide text-[#8b909c]">
                        Description
                      </p>
                      <p className="mt-1 text-sm text-[#e7e9ee]">
                        {result.description}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs uppercase tracking-wide text-[#8b909c]">
                        Recommended action
                      </p>
                      <p className="mt-1 text-sm text-[#e7e9ee]">
                        {result.recommended_action}
                      </p>
                    </div>
                  </div>

                  <div className="md:col-span-2">
                    <p className="mb-2 text-xs uppercase tracking-wide text-[#8b909c]">
                      Detections ({result.num_detections})
                    </p>
                    <div className="space-y-2">
                      {result.detections.map((d, i) => (
                        <div
                          key={i}
                          className="flex items-center justify-between rounded-lg border border-[#1e222b] bg-[#0c0e12] px-3 py-2 text-sm"
                        >
                          <span className="font-medium text-[#e7e9ee]">
                            {d.class_name}
                          </span>
                          <span className="flex gap-4 text-xs text-[#8b909c]">
                            <span>conf {(d.confidence * 100).toFixed(1)}%</span>
                            <span>area {(d.area_fraction * 100).toFixed(1)}%</span>
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </Card>
          )}
        </div>

        {/* RIGHT RAIL */}
        <div className="space-y-6">
          <Card>
            <SectionTitle title="Detection Pipeline" />
            <ol className="space-y-4">
              {PIPELINE.map((s) => (
                <li key={s.n} className="flex gap-3">
                  <span
                    className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold text-white"
                    style={{ background: s.color }}
                  >
                    {s.n}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-medium text-[#e7e9ee]">
                        {s.name}
                      </p>
                      <span className="font-mono text-xs text-[#8b909c]">
                        {s.time}
                      </span>
                    </div>
                    <p className="mt-0.5 text-xs leading-relaxed text-[#8b909c]">
                      {s.desc}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          </Card>

          <Card>
            <SectionTitle
              title="YOLOv8 Model Card"
              right={<Cpu className="h-4 w-4 text-[#8b909c]" />}
            />
            <dl className="space-y-2.5">
              {MODEL_CARD.map((row) => (
                <div
                  key={row.k}
                  className="flex items-start justify-between gap-4 text-sm"
                >
                  <dt className="text-[#8b909c]">{row.k}</dt>
                  <dd className="text-right font-medium text-[#e7e9ee]">
                    {row.v}
                  </dd>
                </div>
              ))}
            </dl>
          </Card>
        </div>
      </div>

      <style jsx>{`
        :global(.input) {
          width: 100%;
          border-radius: 0.5rem;
          border: 1px solid #1e222b;
          background: #0c0e12;
          padding: 0.5rem 0.75rem;
          font-size: 0.875rem;
          color: #e7e9ee;
          outline: none;
        }
        :global(.input:focus) {
          border-color: #3b82f6;
        }
      `}</style>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium text-[#8b909c]">
        {label}
      </span>
      {children}
    </label>
  );
}

function KV({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center justify-between gap-4 text-sm">
      <span className="text-[#8b909c]">{k}</span>
      <span className="font-medium text-[#e7e9ee]">{v}</span>
    </div>
  );
}
