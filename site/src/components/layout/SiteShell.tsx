import type { ReactNode } from "react";

import { publicHomeHref } from "#/lib/paths";

interface SiteShellProps {
  readonly children: ReactNode;
}

export function SiteShell({ children }: SiteShellProps) {
  return (
    <div className="site-shell">
      <header className="site-header">
        <a className="brand-mark" href={publicHomeHref()}>
          <span className="brand-glyph" aria-hidden="true">
            S
          </span>
          <span>squinchmods</span>
        </a>
        <span className="header-note">Independent mod projects</span>
      </header>
      <main className="page-width">{children}</main>
      <footer className="site-footer">
        <span>Built for curious players.</span>
        <span>© Squinchmods</span>
      </footer>
    </div>
  );
}
