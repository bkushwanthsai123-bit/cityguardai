"use client";

import dynamic from "next/dynamic";
import { PageHeader } from "@/components/ui/SectionTitle";
import { LoadingBlock } from "@/components/ui/Spinner";

const MapView = dynamic(() => import("@/components/MapView"), {
  ssr: false,
  loading: () => <LoadingBlock label="Loading map..." />,
});

export default function MapPage() {
  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col">
      <PageHeader
        title="Map View"
        subtitle="Geographic distribution of reported incidents across Bengaluru"
      />
      <div className="min-h-0 flex-1">
        <MapView />
      </div>
    </div>
  );
}
