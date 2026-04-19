import "./globals.css";
import type { ReactNode } from "react";
import { Theme } from "@radix-ui/themes";
import { TopHeader } from "@/components/layout/top-header";

export const metadata = {
  title: "Ouroboros",
  description: "Agent orchestration platform.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Theme accentColor="iris" grayColor="slate" radius="medium" appearance="dark">
          <div className="app-shell">
            <TopHeader />
            <div className="app-body">{children}</div>
          </div>
        </Theme>
      </body>
    </html>
  );
}
