"use client";

import { useParams } from "next/navigation";
import { Chat } from "../../../components/Chat";

export default function ChatWindow() {
  const { id } = useParams<{ id: string }>();
  return <Chat projectId={id} standalone />;
}
