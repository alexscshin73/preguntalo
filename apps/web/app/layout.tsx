import "./globals.css";
import type { Metadata } from "next";
import { UiLanguageProvider } from "../components/ui-language";

const appUrl = process.env.NEXT_PUBLIC_APP_URL ?? "https://preguntalo.carroamix.com";

export const metadata: Metadata = {
  title: "PreguntaLo",
  description: "Search and browse service manuals through PreguntaLo.",
  metadataBase: new URL(appUrl),
  alternates: {
    canonical: "/",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body>
        <UiLanguageProvider>{children}</UiLanguageProvider>
      </body>
    </html>
  );
}
