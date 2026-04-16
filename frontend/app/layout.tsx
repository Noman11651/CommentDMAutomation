import type { Metadata } from 'next'
import Link from 'next/link'
import './globals.css'

export const metadata: Metadata = {
  title: 'Instagram DM Automation - Tejas.algo',
  description: 'Manage Instagram comment-to-DM automation',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>
        <header className="sticky top-0 z-50 border-b border-white/10 bg-slate-950/85 backdrop-blur">
          <nav className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 md:px-8">
            <Link href="/" className="text-sm font-semibold text-white/90 hover:text-white">
              Comment DM Automation
            </Link>
            <div className="flex items-center gap-3">
              <Link
                href="/"
                className="rounded-lg border border-white/20 bg-white/10 px-3 py-1.5 text-sm text-white hover:bg-white/20"
              >
                Dashboard
              </Link>
              <Link
                href="/flows"
                className="rounded-lg border border-white/20 bg-white/10 px-3 py-1.5 text-sm text-white hover:bg-white/20"
              >
                Flows
              </Link>
            </div>
          </nav>
        </header>
        {children}
      </body>
    </html>
  )
}
