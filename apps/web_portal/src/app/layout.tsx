import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "../contexts/AuthContext";
import { ProfileProvider } from "../contexts/ProfileContext";
import { LocaleProvider } from "../contexts/LocaleContext";
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
  title: "GramCare AI",
  description: "AI-Powered Telemedicine Ecosystem",
  manifest: "/manifest.json",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <MotionConfigProvider>
          <LocaleProvider>
            <AuthProvider>
              <ProfileProvider>
                <Header />
                {children}
              </ProfileProvider>
            </AuthProvider>
          </LocaleProvider>
        </MotionConfigProvider>
      </body>
    </html>
  );
}
