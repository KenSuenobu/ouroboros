import "./globals.css";
import type { ReactNode } from "react";
import { AppRail } from "@/components/layout/app-rail";
import { AppTopbar } from "@/components/layout/app-topbar";
import { OnboardingWizard } from "@/components/onboarding/wizard";
import { AppThemeProvider } from "@/components/theme/app-theme-provider";

export const metadata = {
  title: "Ouroboros",
  description: "Agent orchestration platform.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <AppThemeProvider>
          <div className="ob-shell">
            <AppRail />
            <div className="ob-region">
              <AppTopbar />
              <div className="ob-content">{children}</div>
            </div>
          </div>
          <OnboardingWizard />
        </AppThemeProvider>
      </body>
    </html>
  );
}
