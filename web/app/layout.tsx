import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Fragment Evidence Workbench",
  description: "Trace real manuscript pages through segmentation, storage, and synthetic damage experiments.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
