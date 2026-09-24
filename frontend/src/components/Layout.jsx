import { useEffect, useRef, useState } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { NotificationBell } from "./AlumniProfileExtras";
import {
  BarChartIcon,
  ClipboardListIcon,
  CreditCardIcon,
  DatabaseIcon,
  FileTextIcon,
  GiftIcon,
  HashIcon,
  LayoutDashboardIcon,
  LogOutIcon,
  MailIcon,
  MenuIcon,
  SettingsIcon,
  SlidersIcon,
  UsersIcon,
  XIcon,
} from "./icons";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { safeAlumniPath } from "../lib/safeUrl";

function focusablesIn(node) {
  if (!node) return [];
  return [...node.querySelectorAll("a, button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])")].filter(
    (el) => !el.hasAttribute("disabled") && el.getAttribute("aria-hidden") !== "true"
  );
}

export function PublicHeader() {
  const [open, setOpen] = useState(false);
  const { user } = useAuth();
  const menuRef = useRef(null);
  const drawerRef = useRef(null);
  const registerTo = user?.status === "Pending" ? "/pending" : "/register";
  const registerLabel = user?.status === "Pending" ? "Check status" : "Upload resume";

  useEffect(() => {
    if (!open) return undefined;
    const drawer = drawerRef.current;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    focusablesIn(drawer)[0]?.focus();

    function onKey(event) {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
        menuRef.current?.focus();
        return;
      }
      if (event.key !== "Tab") return;
      const items = focusablesIn(drawer);
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  return (
    <header className="topbar">
      <a className="skip-link" href="#main">Skip to content</a>
      <div className="topbar-inner">
        <NavLink to="/" className="brand">
          <img src="/assets/CareerSense-Logo.png" alt="" />
          <div>
            <strong>CareerSense</strong>
            <span>AUF Graduate Tracer Portal</span>
          </div>
        </NavLink>
        <nav className="nav-links" aria-label="Primary">
          <a href="/#features">Features</a>
          <a href="/#how">How it works</a>
          <NavLink to="/login">Sign in</NavLink>
          <NavLink to={registerTo} className="btn btn-primary">{registerLabel}</NavLink>
        </nav>
        <button
          className="btn btn-ghost public-menu-btn"
          type="button"
          ref={menuRef}
          aria-expanded={open}
          aria-controls="public-drawer"
          onClick={() => setOpen((value) => !value)}
        >
          Menu
        </button>
      </div>
      {open && (
        <nav className="public-drawer" id="public-drawer" aria-label="Site" ref={drawerRef}>
          <a href="/#features" onClick={() => setOpen(false)}>Features</a>
          <a href="/#how" onClick={() => setOpen(false)}>How it works</a>
          <NavLink to="/login" onClick={() => setOpen(false)}>Sign in</NavLink>
          <NavLink to={registerTo} className="btn btn-primary public-drawer-cta" onClick={() => setOpen(false)}>
            {registerLabel}
          </NavLink>
        </nav>
      )}
    </header>
  );
}

export function PublicFooter() {
  return (
    <footer className="footer">
      <div className="footer-inner">
        <div>
          <strong>Alumni Affairs and Placement Services (AAPS)</strong>
          <div><small>Angeles University Foundation · CareerSense Graduate Tracer System</small></div>
        </div>
        <small>Personal data is processed under the Data Privacy Act of 2012 (RA 10173).</small>
      </div>
    </footer>
  );
}

const ALUMNI_NAV = [
  { label: "Home", items: [["Home", "/alumni", LayoutDashboardIcon]] },
  {
    label: "Services",
    items: [
      ["Alumni Card", "/alumni/card", CreditCardIcon],
      ["Perks & Discounts", "/alumni/perks", GiftIcon],
    ],
  },
  {
    label: "My Record",
    items: [["Resume & Tracer", "/alumni/resume", FileTextIcon]],
  },
  { label: "Account", items: [["Account", "/alumni/account", SettingsIcon]] },
];

const ADMIN_NAV = [
  { label: "Home", items: [["Dashboard", "/admin", LayoutDashboardIcon]] },
  {
    label: "Operations",
    items: [
      ["Approvals", "/admin/approvals", ClipboardListIcon],
      ["Alumni Cards", "/admin/cards", CreditCardIcon],
      ["Profile Updates", "/admin/profile-updates", MailIcon],
      ["Records", "/admin/records", FileTextIcon],
      ["Registry", "/admin/registry", DatabaseIcon],
      ["Reports", "/admin/reports", BarChartIcon],
    ],
  },
  {
    label: "Setup",
    items: [
      ["Survey", "/admin/survey", SlidersIcon],
      ["Perks", "/admin/perks", GiftIcon],
      ["SOC Mapping", "/admin/soc", HashIcon],
      ["Users", "/admin/users", UsersIcon],
      ["Account", "/admin/account", SettingsIcon],
    ],
  },
];

function pageLabel(pathname, hash, groups, fallback) {
  if (/^\/admin\/approvals\/\d+/.test(pathname)) return "Registration Review";
  if (/^\/admin\/records\/\d+/.test(pathname)) return "Tracer Record Details";
  const items = groups.flatMap((group) => group.items);
  const currentHash = hash || "";
  if (currentHash) {
    const hashed = items.find(([, to]) => to === `${pathname}${currentHash}`);
    if (hashed) return hashed[0];
  }
  const exact = items.find(([, to]) => to === pathname);
  if (exact) return exact[0];
  const nested = items
    .filter(([, to]) => !to.includes("#") && pathname.startsWith(`${to}/`))
    .sort((a, b) => b[1].length - a[1].length)[0];
  return nested?.[0] || fallback;
}

function navTarget(to) {
  if (to.includes("#")) {
    const [pathname, frag] = to.split("#");
    return { pathname, hash: `#${frag}` };
  }
  return { pathname: to, hash: "" };
}

function navItemActive(to, pathname) {
  if (to === "/admin") return pathname === "/admin";
  if (to === "/alumni") return pathname === "/alumni";
  return pathname === to || pathname.startsWith(`${to}/`);
}

function initialsFromEmail(email) {
  const local = String(email || "").split("@")[0];
  const parts = local.split(/[.\-_]/).filter(Boolean);
  if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  return (local.slice(0, 2) || "A").toUpperCase();
}

function initialsFromUser(user) {
  const first = String(user?.first_name || "").trim();
  const last = String(user?.last_name || "").trim();
  if (first && last) return `${first[0]}${last[0]}`.toUpperCase();
  if (first) return first.slice(0, 2).toUpperCase();
  return initialsFromEmail(user?.personal_email);
}

export function PortalShell({ role, children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [navOpen, setNavOpen] = useState(false);
  const [notes, setNotes] = useState([]);
  const [notesState, setNotesState] = useState("idle");
  const menuRef = useRef(null);
  const sidebarRef = useRef(null);
  const groups = role === "Admin" ? ADMIN_NAV : ALUMNI_NAV;
  const title = role === "Admin" ? "Administrator" : "Alumni Portal";
  const home = role === "Admin" ? "/admin" : "/alumni";
  const currentPage = pageLabel(location.pathname, location.hash, groups, "Dashboard");
  const displayName = [user?.first_name, user?.last_name].filter(Boolean).join(" ") || user?.personal_email || "Alumni";
  const initials = initialsFromUser(user);
  const accountTo = role === "Admin" ? "/admin/account" : "/alumni/account";

  useEffect(() => {
    const previous = document.title;
    document.title = `${currentPage} · CareerSense`;
    return () => {
      document.title = previous;
    };
  }, [currentPage]);

  useEffect(() => {
    setNavOpen(false);
  }, [location.pathname, location.hash]);

  useEffect(() => {
    if (role !== "Alumni") return undefined;
    let cancelled = false;
    setNotesState("loading");
    api("/api/alumni/notifications")
      .then((data) => {
        if (cancelled) return;
        setNotes(data.notifications || []);
        setNotesState("ready");
      })
      .catch(() => {
        if (cancelled) return;
        setNotes([]);
        setNotesState("error");
      });
    return () => {
      cancelled = true;
    };
  }, [role, location.pathname]);

  useEffect(() => {
    if (!navOpen) return undefined;
    const sidebar = sidebarRef.current;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const items = focusablesIn(sidebar);
    items[0]?.focus();

    function onKey(event) {
      if (event.key === "Escape") {
        event.preventDefault();
        setNavOpen(false);
        menuRef.current?.focus();
        return;
      }
      if (event.key !== "Tab") return;
      const items = focusablesIn(sidebar);
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
    };
  }, [navOpen]);

  async function readOne(item) {
    const to = safeAlumniPath(item.link);
    if (to) navigate(to);
    if (item.read) return;
    try {
      const result = await api(`/api/alumni/notifications/${item.id}/read`, { method: "POST" });
      setNotes(result.notifications || []);
    } catch {
      setNotes((current) => current.map((row) => (row.id === item.id ? { ...row, read: true } : row)));
    }
  }

  async function readAll() {
    try {
      const result = await api("/api/alumni/notifications/read-all", { method: "POST" });
      setNotes(result.notifications || []);
    } catch {
      setNotes((current) => current.map((row) => ({ ...row, read: true })));
    }
  }

  function closeNav() {
    setNavOpen(false);
  }

  return (
    <div className={`app-shell ${role === "Alumni" ? "is-alumni" : "is-admin"} ${navOpen ? "nav-open" : ""}`} id="portal-shell">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <aside className="sidebar" ref={sidebarRef} id="portal-sidebar">
        <div className="sidebar-brand-row">
          <NavLink to={{ pathname: home, hash: "" }} end className="brand" onClick={closeNav}>
            <img src="/assets/CareerSense-Logo.png" alt="" />
            <div>
              <strong>CareerSense</strong>
              <span>{title}</span>
            </div>
          </NavLink>
          <button
            className="btn btn-ghost sidebar-close"
            type="button"
            aria-label="Close navigation"
            onClick={closeNav}
          >
            <XIcon size={18} />
          </button>
        </div>
        <nav className="sidebar-nav" aria-label={title}>
          {groups.map((group) => (
            <div className="nav-group" key={group.label}>
              <p className="nav-group-label">{group.label}</p>
              {group.items.map(([label, to, Icon]) => {
                const active = navItemActive(to, location.pathname);
                return (
                  <Link
                    key={to}
                    to={navTarget(to)}
                    className={`side-link ${active ? "active" : ""}`}
                    aria-current={active ? "page" : undefined}
                    onClick={closeNav}
                  >
                    {Icon ? <Icon size={18} /> : null}
                    <span>{label}</span>
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="side-user-card">
            <span className="side-avatar" aria-hidden="true">{initials}</span>
            <div className="side-user">
              <span className="side-user-name">{displayName}</span>
              <span className="side-user-role">{role === "Admin" ? "Administrator" : "Alumni"}</span>
            </div>
          </div>
          <button
            className="btn btn-ghost btn-block sign-out-btn"
            type="button"
            onClick={() => {
              logout();
              navigate("/login");
            }}
          >
            <LogOutIcon size={16} />
            Sign out
          </button>
        </div>
      </aside>
      {navOpen ? (
        <button type="button" className="nav-backdrop" aria-label="Close menu" onClick={closeNav} />
      ) : null}
      <div className="main">
        <div className="portal-top">
          <button
            className="btn btn-outline portal-menu-btn"
            type="button"
            ref={menuRef}
            aria-expanded={navOpen}
            aria-controls="portal-sidebar"
            aria-label={navOpen ? "Close navigation" : "Open navigation"}
            onClick={() => setNavOpen((value) => !value)}
          >
            <MenuIcon size={18} />
            <span className="portal-menu-label">Menu</span>
          </button>
          <div className="portal-top-copy">
            <span className="portal-top-kicker">{title}</span>
            <strong>{currentPage}</strong>
          </div>
          {role === "Alumni" ? (
            <div className="portal-top-tools">
              <NotificationBell
                items={notes}
                loading={notesState === "loading"}
                error={notesState === "error"}
                onRead={readOne}
                onReadAll={readAll}
                onRetry={() => {
                  setNotesState("loading");
                  api("/api/alumni/notifications")
                    .then((data) => {
                      setNotes(data.notifications || []);
                      setNotesState("ready");
                    })
                    .catch(() => setNotesState("error"));
                }}
              />
              <Link to={accountTo} className="portal-identity-link" title="Manage account">
                <span className="portal-avatar" aria-hidden="true">{initials}</span>
                <span className="portal-identity">
                  <strong>{displayName}</strong>
                </span>
              </Link>
            </div>
          ) : (
            <Link to={accountTo} className="portal-identity-link" title="Account">
              <span className="portal-avatar" aria-hidden="true">{initials}</span>
              <span className="portal-identity">
                <strong>{displayName}</strong>
              </span>
            </Link>
          )}
        </div>
        <div className="main-inner" id="main-content" tabIndex={-1}>
          {children}
        </div>
      </div>
    </div>
  );
}
