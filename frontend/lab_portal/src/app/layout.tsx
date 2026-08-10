import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "../contexts/AuthContext";
import Header from "../components/Header";
import MotionConfigProvider from "../components/MotionConfigProvider";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "GramCare Lab Portal",
  description: "Laboratory booking, sample tracking, and report management for GramCare AI",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col relative">
        <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
          <div className="absolute top-[-15%] right-[-10%] w-[520px] h-[520px] bg-violet-500 rounded-full mix-blend-multiply filter blur-[120px] opacity-10" />
          <div className="absolute bottom-[-15%] left-[-10%] w-[420px] h-[420px] bg-purple-400 rounded-full mix-blend-multiply filter blur-[110px] opacity-10" />
        </div>
        <MotionConfigProvider>
          <AuthProvider>
            <Header />
            {children}
          </AuthProvider>
        </MotionConfigProvider>
      </body>
    </html>
  );
}
