import type { Metadata } from "next";
import Workspace from "./workspace";

export const metadata: Metadata = {
  title: "Ticket workspace",
  description:
    "Analyze a fictional support ticket, inspect original sources, and review the proposed internal note.",
};

export default function WorkspacePage() {
  return <Workspace />;
}
