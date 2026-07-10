import { type ReactNode } from "react";
import { Card } from "../ui/Card";

interface Props {
  title: string;
  icon?: ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
}

// Thin wrapper over the Card primitive (spec §4). Kept as a named component so the many
// sidebar cards (PropertyCard, NeighborhoodCard, …) need no change while inheriting the
// unified chrome. New code should use <Card collapsible> directly.
export function CollapsibleCard({ title, icon, defaultOpen = true, children }: Props) {
  return (
    <Card collapsible title={title} icon={icon} defaultOpen={defaultOpen} padding="sm">
      {children}
    </Card>
  );
}
