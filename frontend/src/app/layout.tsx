import type { Metadata } from "next";
import { Plus_Jakarta_Sans } from "next/font/google";
import { EnvironmentProvider } from "@/lib/environment";
import { ThemeProvider } from "@/lib/theme";
import "./globals.css";

const jakarta = Plus_Jakarta_Sans({
  variable: "--font-jakarta",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "Trustanova",
  description: "Identity verification & compliance dashboard",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${jakarta.variable} antialiased`}>
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('trustanova_theme')||'system';var r=t==='light'||t==='dark'?t:(window.matchMedia('(prefers-color-scheme: light)').matches?'light':'dark');document.documentElement.setAttribute('data-theme',r);document.documentElement.style.colorScheme=r;}catch(e){}})();`,
          }}
        />
        <ThemeProvider>
          <EnvironmentProvider>{children}</EnvironmentProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
