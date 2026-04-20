"use client";

import { Badge, Box, Flex, Text } from "@radix-ui/themes";
import { CheckCircle2 } from "lucide-react";
import { PageHeader } from "@/components/layout/page-shell";
import { useProviders } from "@/lib/api/hooks";
import type { Provider } from "@/lib/api/types";

const HEALTH_LABEL: Record<NonNullable<Provider["last_health_status"]>, string> = {
  ok: "ok",
  unreachable: "unreachable",
  unauthorized: "unauthorized",
  "no-models": "no models",
};

const HEALTH_COLOR: Record<NonNullable<Provider["last_health_status"]>, "green" | "red" | "orange" | "gray"> = {
  ok: "green",
  unreachable: "red",
  unauthorized: "orange",
  "no-models": "gray",
};

export default function ProviderHealthPage() {
  const { data: providers = [] } = useProviders();
  const allGreen = providers.length > 0 && providers.every((provider) => provider.last_health_status === "ok");

  return (
    <main className="app-main">
      <PageHeader
        title="Provider health"
        subtitle="Latest probe results for every configured provider"
        actions={
          allGreen ? (
            <Flex align="center" gap="2">
              <CheckCircle2 size={16} color="var(--green-10)" />
              <Text size="2" color="green">All providers healthy</Text>
            </Flex>
          ) : null
        }
      />
      <Flex direction="column" gap="3">
        {providers.map((provider) => (
          <Box key={provider.id} style={{ border: "1px solid var(--gray-a5)", borderRadius: 10, padding: 12 }}>
            <Flex align="center" justify="between" gap="3">
              <Flex direction="column" gap="1">
                <Text size="3" weight="medium">{provider.name}</Text>
                <Text size="1" color="gray">{provider.kind}</Text>
              </Flex>
              <HealthBadge provider={provider} />
            </Flex>
            {provider.last_health_error ? (
              <Text size="1" color="gray" style={{ marginTop: 8, display: "block" }}>
                {provider.last_health_error}
              </Text>
            ) : null}
          </Box>
        ))}
        {providers.length === 0 ? (
          <Text size="2" color="gray">No providers configured yet.</Text>
        ) : null}
      </Flex>
    </main>
  );
}

function HealthBadge({ provider }: { provider: Provider }) {
  const status = provider.last_health_status;
  if (!status) {
    return <Badge color="gray">unknown</Badge>;
  }

  return (
    <Badge color={HEALTH_COLOR[status]} title={provider.last_health_error || ""}>
      {HEALTH_LABEL[status]}
    </Badge>
  );
}
