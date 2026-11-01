"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useProject } from "../../../../../components/ProjectShell";
import { RunPanel } from "../../../../../components/RunPanel";

export default function RunPage() {
  const { project, refresh } = useProject();
  const { runId } = useParams<{ runId: string }>();
  return (
    <>
      <Link href={`/projects/${project.id}/runs`} className="mb-2 inline-flex items-center gap-1 text-xs text-slate-500 hover:text-indigo-500"><ArrowLeft className="h-3 w-3" /> Runs</Link>
      <RunPanel runId={runId} projectId={project.id} onFinished={refresh} />
    </>
  );
}
