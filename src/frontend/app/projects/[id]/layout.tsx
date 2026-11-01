import { ProjectShell } from "../../../components/ProjectShell";

export default function Layout({ children }: { children: React.ReactNode }) {
  return <ProjectShell>{children}</ProjectShell>;
}
