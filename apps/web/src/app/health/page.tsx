"use client";

import { Box, Flex, Text } from "@radix-ui/themes";
import { CheckCircle2 } from "lucide-react";
import { PageHeader } from "@/components/layout/page-shell";
import { HealthBadge } from "@/components/provider-health-badge";
import { useProviders } from "@/lib/api/hooks";

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
