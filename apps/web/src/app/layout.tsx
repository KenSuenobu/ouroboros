import "./globals.css";
import type { ReactNode } from "react";
import { TopHeader } from "@/components/layout/top-header";
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
          <div className="app-shell">
            <TopHeader />
            <div className="app-body">{children}</div>
          </div>
        </AppThemeProvider>
      </body>
    </html>
  );
}
