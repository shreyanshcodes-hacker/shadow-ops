import type { Metadata } from 'next';
import { Inter, JetBrains_Mono } from 'next/font/google';
import './globals.css';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-jetbrains-mono',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'ShadowOps - Your AI Security Team',
  description: 'Continuous security monitoring for startups and engineering teams',
  keywords: ['security', 'vulnerability', 'scanning', 'AI', 'DevSecOps'],
  authors: [{ name: 'ShadowOps' }],
  metadataBase: new URL('https://app.shadowops.io'),
  openGraph: {
    title: 'ShadowOps - Your AI Security Team',
    description: 'Continuous security monitoring for startups and engineering teams',
    type: 'website',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" class={`${inter.variable} ${jetbrainsMono.variable} dark`}>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body className="min-h-screen bg-background-DEFAULT text-foreground-DEFAULT font-sans">
        {children}
      </body>
    </html>
  );
}