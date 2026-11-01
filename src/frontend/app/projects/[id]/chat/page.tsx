"use client";

import { Chat } from "../../../../components/Chat";
import { useProject } from "../../../../components/ProjectShell";

export default function ChatPage() {
  const { project } = useProject();
  return <Chat projectId={project.id} />;
}
