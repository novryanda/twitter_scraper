"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  LayoutDashboard, Search, TrendingUp, Bug, KeyRound, Twitter,
  MessageCircle, ChevronLeft, ChevronRight, Menu, X,
} from "lucide-react";
import { api } from "@/lib/api";

const NAV = [
  { href: "/dashboard", label: "Dashboard",       icon: LayoutDashboard },
  { href: "/scrape",    label: "Scrape Profil",   icon: Search          },
  { href: "/tweets",    label: "Scrape Tweet",    icon: MessageCircle   },
  { href: "/tracking",  label: "Growth Tracking", icon: TrendingUp      },
  { href: "/login",     label: "Session / Login", icon: KeyRound        },
  { href: "/debug",     label: "Debug Panel",     icon: Bug             },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [online,      setOnline]      = useState<boolean | null>(null);
  const [loggedIn,    setLoggedIn]    = useState(false);
  const [username,    setUsername]    = useState("");
  const [collapsed,   setCollapsed]   = useState(false);
  const [mobileOpen,  setMobileOpen]  = useState(false);

  useEffect(() => {
    try {
      const saved = localStorage.getItem("sidebar-collapsed");
      if (saved === "true") setCollapsed(true);
    } catch { /* ignore */ }
  }, []);

  const toggleCollapse = () => {
    setCollapsed(c => {
      const next = !c;
      try { localStorage.setItem("sidebar-collapsed", String(next)); } catch { /* ignore */ }
      return next;
    });
  };

  // Close mobile sidebar on route change
  useEffect(() => { setMobileOpen(false); }, [pathname]);

  useEffect(() => {
    let active = true;
    const check = async () => {
      const h = await api.health();
      if (!active) return;
      setOnline(h.success);
      if (h.success) {
        const s = await api.authStatus();
        if (!active) return;
        setLoggedIn(s.data?.is_logged_in || false);
        setUsername(s.data?.username || "");
      }
    };
    check();
    const t = setInterval(check, 8000);
    return () => { active = false; clearInterval(t); };
  }, []);

  const sidebarWidth = collapsed ? 70 : 256;

  return (
    <>
      {/* Mobile top bar */}
      <button
        className="sidebar-mobile-trigger"
        onClick={() => setMobileOpen(o => !o)}
        aria-label="Toggle menu"
      >
        <Menu size={20} />
      </button>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="sidebar-backdrop"
          onClick={() => setMobileOpen(false)}
        />
      )}

      <aside
        className={`sidebar${collapsed ? " sidebar--collapsed" : ""}${mobileOpen ? " sidebar--mobile-open" : ""}`}
        style={{ width: sidebarWidth }}
      >
        {/* Header: logo + collapse button */}
        <div className="sidebar-header">
          <Link href="/dashboard" style={{ textDecoration: "none", display: "flex", alignItems: "center", gap: 11, overflow: "hidden", flex: 1, minWidth: 0 }}>
            <div className="sidebar-logo-icon">
              <Twitter size={20} color="#fff" />
            </div>
            {!collapsed && (
              <div className="sidebar-logo-text">
                <span className="sidebar-logo-title">X Scraper</span>
                <span className="sidebar-logo-sub">Growth Analytics</span>
              </div>
            )}
          </Link>

          <button
            className="sidebar-collapse-btn"
            onClick={toggleCollapse}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
          </button>
        </div>

        {/* Mobile close button */}
        <button
          className="sidebar-mobile-close"
          onClick={() => setMobileOpen(false)}
        >
          <X size={18} />
        </button>

        {/* Nav */}
        <nav className="sidebar-nav">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href));
            return (
              <Link key={href} href={href} style={{ textDecoration: "none" }}>
                <div
                  className={`sidebar-item glass-hover${active ? " sidebar-item--active" : ""}`}
                  title={collapsed ? label : undefined}
                >
                  <span className="sidebar-item-icon">
                    <Icon size={18} color={active ? "var(--accent-cyan)" : "currentColor"} />
                  </span>
                  {!collapsed && <span className="sidebar-item-label">{label}</span>}
                </div>
              </Link>
            );
          })}
        </nav>

        {/* Status footer */}
        <div className="glass sidebar-footer">
          <div className="sidebar-status-row" title={collapsed ? (online ? "Backend Online" : "Backend Offline") : undefined}>
            <span className={`dot ${online ? "dot-green dot-pulse" : "dot-red"}`} />
            {!collapsed && (
              <span className="sidebar-status-label">
                Backend {online === null ? "…" : online ? "Online" : "Offline"}
              </span>
            )}
          </div>
          <div className="sidebar-status-row" style={{ marginTop: 8 }} title={collapsed ? (loggedIn ? `@${username || "logged in"}` : "Belum login") : undefined}>
            <span className={`dot ${loggedIn ? "dot-green" : "dot-red"}`} />
            {!collapsed && (
              <span className="sidebar-status-label sidebar-status-sub">
                {loggedIn ? `@${username || "logged in"}` : "Belum login"}
              </span>
            )}
          </div>
        </div>
      </aside>
    </>
  );
}
