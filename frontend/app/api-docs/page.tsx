"use client";

import { ExternalLink } from "lucide-react";
import { API } from "@/lib/api";
import { PageHeader, SectionTitle } from "@/components/ui/SectionTitle";
import { Card } from "@/components/ui/Card";

type Method = "GET" | "POST" | "PATCH" | "DELETE";

interface Endpoint {
  method: Method;
  path: string;
  desc: string;
}

interface Group {
  name: string;
  endpoints: Endpoint[];
}

const GROUPS: Group[] = [
  {
    name: "Detection",
    endpoints: [
      {
        method: "POST",
        path: "/detect",
        desc: "Run YOLOv8 + Llama 3.2 on an uploaded image and persist an incident.",
      },
      {
        method: "POST",
        path: "/detect/batch",
        desc: "Run detection across multiple uploaded images.",
      },
    ],
  },
  {
    name: "Incidents",
    endpoints: [
      {
        method: "GET",
        path: "/incidents",
        desc: "List incidents with optional severity/status/department/priority filters.",
      },
      {
        method: "GET",
        path: "/incidents/{id}",
        desc: "Fetch a single incident by id.",
      },
      {
        method: "PATCH",
        path: "/incidents/{id}",
        desc: "Update an incident's status (open, in_progress, resolved).",
      },
      {
        method: "DELETE",
        path: "/incidents/{id}",
        desc: "Delete an incident by id.",
      },
    ],
  },
  {
    name: "Analytics",
    endpoints: [
      {
        method: "GET",
        path: "/analytics/summary",
        desc: "Aggregate counts by severity, department, status, priority, plus a daily trend.",
      },
      {
        method: "GET",
        path: "/analytics/hotspots",
        desc: "Geographic clusters of incidents with counts and top severity.",
      },
    ],
  },
  {
    name: "System",
    endpoints: [
      {
        method: "GET",
        path: "/health",
        desc: "Liveness probe: model loaded, DB connectivity, Ollama status.",
      },
      { method: "GET", path: "/", desc: "Service banner and docs link." },
    ],
  },
];

const METHOD_COLORS: Record<Method, string> = {
  GET: "#22c55e",
  POST: "#3b82f6",
  PATCH: "#eab308",
  DELETE: "#ef4444",
};

const CURL = `curl -X POST ${API}/detect \\
  -F "file=@street.jpg" \\
  -F "lat=12.9758" \\
  -F "lon=77.6045" \\
  -F "address=MG Road, Bengaluru"`;

export default function ApiDocsPage() {
  return (
    <div>
      <PageHeader
        title="API Documentation"
        subtitle="REST reference for the CityGuard AI FastAPI backend"
        right={
          <a
            href={`${API}/docs`}
            target="_blank"
            rel="noreferrer"
            className="brand-gradient inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-white shadow-lg shadow-blue-500/20"
          >
            Open Swagger UI
            <ExternalLink className="h-4 w-4" />
          </a>
        }
      />

      <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2">
        {GROUPS.map((group) => (
          <Card key={group.name}>
            <SectionTitle title={group.name} />
            <ul className="space-y-2.5">
              {group.endpoints.map((ep) => (
                <li
                  key={`${ep.method}-${ep.path}`}
                  className="rounded-lg border border-[#1e222b] bg-[#0c0e12] px-3 py-2.5"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className="inline-flex w-16 justify-center rounded-md px-2 py-0.5 text-xs font-semibold"
                      style={{
                        background: `${METHOD_COLORS[ep.method]}1f`,
                        color: METHOD_COLORS[ep.method],
                        border: `1px solid ${METHOD_COLORS[ep.method]}4d`,
                      }}
                    >
                      {ep.method}
                    </span>
                    <code className="font-mono text-sm text-[#e7e9ee]">
                      {ep.path}
                    </code>
                  </div>
                  <p className="mt-1.5 text-xs leading-relaxed text-[#8b909c]">
                    {ep.desc}
                  </p>
                </li>
              ))}
            </ul>
          </Card>
        ))}
      </div>

      <Card>
        <SectionTitle
          title="Sample request"
          subtitle="Submit an image to the detection pipeline"
        />
        <pre className="overflow-x-auto rounded-lg border border-[#1e222b] bg-[#0c0e12] p-4 font-mono text-xs leading-relaxed text-[#e7e9ee]">
          {CURL}
        </pre>
        <p className="mt-3 text-xs text-[#8b909c]">
          The response is an Incident object with detections, an LLM-generated
          report (severity, priority, department, recommended action), and SLA.
        </p>
      </Card>
    </div>
  );
}
