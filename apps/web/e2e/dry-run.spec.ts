import { test, expect, type Route } from "@playwright/test";

/**
 * End-to-end smoke that walks through a fake dry-run against a mock provider.
 *
 * The web app is started normally, but every `/api/*` call is intercepted and
 * answered from this file. That keeps the test self-contained: no FastAPI, no
 * provider, no network.
 */

const FAKE_RUN = {
  id: "run-1",
  workspace_id: "ws-1",
  project_id: "proj-1",
  flow_id: "flow-1",
  issue_id: null,
  issue_number: 42,
  title: "Run for issue #42",
  status: "succeeded",
  dry_run: true,
  started_at: new Date().toISOString(),
  finished_at: new Date().toISOString(),
  total_tokens_in: 120,
  total_tokens_out: 240,
  cost_estimate_usd: 0.0042,
  plan: { nodes: [{ id: "planner", type: "agent", label: "Planner", position: { x: 0, y: 0 } }], edges: [] },
  error: null,
  steps: [
    {
      id: "s1",
      run_id: "run-1",
      node_id: "planner",
      agent_id: "a1",
      sequence: 1,
      attempt: 1,
      status: "succeeded",
      started_at: new Date().toISOString(),
      finished_at: new Date().toISOString(),
      provider_id: "p1",
      model_used: "fake-model",
      tokens_in: 120,
      tokens_out: 240,
      cost_estimate_usd: 0.0042,
      summary: "Planned 3 steps",
      error: null,
      dry_run: true,
    },
  ],
};

test("can view a dry-run and see the promote button", async ({ page }) => {
  await page.route("**/api/runs/run-1", async (route: Route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(FAKE_RUN) });
  });
  await page.route("**/api/runs/run-1/interventions", async (route: Route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route("**/api/runs/run-1/steps/**/artifacts", async (route: Route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });

  await page.goto("/runs/run-1");

  await expect(page.getByText("Run for issue #42")).toBeVisible();
  await expect(page.getByText(/dry-run/i)).toBeVisible();
  await expect(page.getByRole("button", { name: /Promote to real run/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /Export summary\.md/i })).toBeVisible();
});
