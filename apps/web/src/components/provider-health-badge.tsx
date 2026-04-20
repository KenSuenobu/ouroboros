import { Badge } from "@radix-ui/themes";
import type { Provider } from "@/lib/api/types";

export const HEALTH_LABEL: Record<NonNullable<Provider["last_health_status"]>, string> = {
  ok: "ok",
  unreachable: "unreachable",
  unauthorized: "unauthorized",
  "no-models": "no models",
  unsupported: "unsupported",
};

export const HEALTH_COLOR: Record<
  NonNullable<Provider["last_health_status"]>,
  "green" | "red" | "orange" | "gray"
> = {
  ok: "green",
  unreachable: "red",
  unauthorized: "orange",
  "no-models": "gray",
  unsupported: "gray",
};

export function HealthBadge({ provider, onClick }: { provider: Provider; onClick?: () => void }) {
  const status = provider.last_health_status;
  const badge = !status ? (
    <Badge color="gray" title="No health check yet">
      unknown
    </Badge>
  ) : (
    <Badge color={HEALTH_COLOR[status]} title={provider.last_health_error || ""}>
      {HEALTH_LABEL[status]}
    </Badge>
  );

  if (!onClick) return badge;

  return (
    <button
      type="button"
      onClick={onClick}
      style={{ background: "transparent", border: 0, padding: 0, margin: 0, cursor: "pointer" }}
    >
      {badge}
    </button>
  );
}
