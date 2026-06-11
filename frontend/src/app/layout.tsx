import type { Metadata } from "next";
import AuroraBackground from "@/components/AuroraBackground";
import Sidebar from "@/components/Sidebar";
import { ToastProvider } from "@/components/Toast";
import { JobProvider } from "@/components/JobContext";
import { JobBanner } from "@/components/JobBanner";

// ── Fix: import CSS lewat file globals terpisah, bukan langsung di sini ──────
// Jika globals.css ada di src/styles/, import-nya di _app.tsx atau globals.ts.
// Di Next.js 13+ App Router, CSS global diimport di sini tapi harus .css murni.
// Kalau masih error TS2882, tambahkan deklarasi di src/types/css.d.ts (lihat bawah).
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "X Scraper — Growth Analytics",
  description: "Twitter/X profile scraper dengan glassmorphism UI",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <body>
        <AuroraBackground />
        <ToastProvider>
          <JobProvider>
            <div style={{ display: "flex", minHeight: "100vh" }}>
              <Sidebar />
              <main className="layout-main" style={{ flex: 1, padding: "32px 36px 60px", minWidth: 0 }}>
                {/* Banner muncul otomatis di semua halaman saat ada job aktif */}
                <JobBanner />
                {children}
              </main>
            </div>
          </JobProvider>
        </ToastProvider>
      </body>
    </html>
  );
}