import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/Sidebar";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "CityGuard AI — Smart City System",
  description:
    "City-wide illegal dumping detection powered by YOLOv8 and a local Llama 3.2 LLM.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} antialiased`}
    >
      <body className="bg-[#0a0b0e] text-[#e7e9ee]">
        <Sidebar />
        <main className="ml-[272px] min-h-screen">
          <div className="mx-auto max-w-[1400px] px-8 py-8">{children}</div>
        </main>
      </body>
    </html>
  );
}
