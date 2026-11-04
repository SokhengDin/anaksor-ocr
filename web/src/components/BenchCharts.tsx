import { asset } from "@/lib/config";

export function BenchCharts({ alt, accuracyNote, speedNote }: { alt: [string, string, string]; accuracyNote: string; speedNote: string }) {
  const [detection, recognition, speed] = alt;
  return (
    <div className="bench">
      <p>{accuracyNote}</p>
      {/* eslint-disable-next-line @next/next/no-img-element -- plain files from public/ */}
      <img src={asset("/bench/bench-detection.png")} alt={detection} width={2000} height={1080} loading="lazy" />
      {/* eslint-disable-next-line @next/next/no-img-element -- plain files from public/ */}
      <img src={asset("/bench/bench-recognition.png")} alt={recognition} width={2000} height={1080} loading="lazy" />
      {/* eslint-disable-next-line @next/next/no-img-element -- plain files from public/ */}
      <img src={asset("/bench/bench-speed.png")} alt={speed} width={2000} height={1080} loading="lazy" />
      <p>{speedNote}</p>
    </div>
  );
}
