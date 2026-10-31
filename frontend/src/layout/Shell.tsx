import {
  Compass,
  FlaskConical,
  Heart,
  Library,
  ListMusic,
  ScanFace,
  Settings,
  SlidersHorizontal,
  Sparkles,
  type LucideIcon,
} from "lucide-react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";

import { usePlayer } from "../lib/store";
import { PlayerBar } from "./PlayerBar";
import { RightRail } from "./RightRail";

const LINKS = [
  { to: "/", label: "For You", icon: Sparkles },
  { to: "/discover", label: "Discover", icon: Compass },
  { to: "/mood", label: "Mood Studio", icon: ScanFace },
  { to: "/lab", label: "Model Lab", icon: FlaskConical },
];

const LIBRARY = [
  { to: "/playlist", label: "Playlist", icon: ListMusic },
  { to: "/library", label: "My Library", icon: Library },
  { to: "/liked", label: "Liked Songs", icon: Heart },
  { to: "/taste", label: "My Taste", icon: SlidersHorizontal },
];

export function Shell() {
  const location = useLocation();
  const profile = usePlayer((state) => state.profile);
  const provider = usePlayer((state) => state.catalog[0]?.provider);
  const [queueOpen, setQueueOpen] = useState(false);
  const catalogLabel = provider === "itunes" ? "Apple Music" : provider === "youtube" ? "YouTube" : provider === "demo" ? "Demo catalog" : "Catalog";
  const profileLabel = profile?.collaborative_unlocked
    ? "Hybrid profile"
    : (profile?.inferred.n_events ?? 0) > 0
      ? "Listening profile"
      : "Onboarding profile";

  return (
    <div className="flex h-full flex-col">
      <div className="flex min-h-0 flex-1">
        <nav className="hidden w-[228px] shrink-0 flex-col border-r border-white/8 bg-ink/70 px-3 py-5 md:flex">
          <div className="px-3">
            <div className="font-display text-[28px] leading-none tracking-tight text-foam">Moodwave</div>
            <div className="mt-2 text-[11px] uppercase tracking-[0.2em] text-mist">{catalogLabel}</div>
          </div>
          <div className="mt-8 flex flex-col gap-1">
            {LINKS.map((link) => (
              <Item key={link.to} {...link} />
            ))}
          </div>
          <div className="mt-8 px-3 text-[11px] uppercase tracking-[0.18em] text-mist">Library</div>
          <div className="mt-2 flex flex-col gap-1">
            {LIBRARY.map((link) => (
              <Item key={link.to} {...link} />
            ))}
          </div>
          <div className="mt-auto px-1">
            <Item to="/settings" label="Settings" icon={Settings} />
            <div className="mt-4 rounded-2xl border border-white/8 px-3 py-3">
              <div className="text-sm text-foam">Listener</div>
              <div className="mt-1 text-xs leading-5 text-mist">
                {profileLabel} · confidence{" "}
                {Math.round((profile?.inferred.confidence ?? 0) * 100)}%
              </div>
            </div>
          </div>
        </nav>
        <main className="min-w-0 flex-1 overflow-y-auto">
          <div className="flex items-center justify-between px-6 pt-4 md:hidden">
            <div className="font-display text-2xl">Moodwave</div>
            <button className="text-sm text-sand" onClick={() => setQueueOpen(true)}>
              <ListMusic size={16} className="mr-1 inline" />
              Queue
            </button>
          </div>
          <div className="hidden justify-end px-6 pt-3 md:flex xl:hidden">
            <button className="rounded-full border border-white/10 px-3 py-1 text-xs text-mist" onClick={() => setQueueOpen(true)}>
              Queue
            </button>
          </div>
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.22 }}
              className="px-6 pb-10 pt-4 md:px-10"
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </main>
        <div className="hidden w-[320px] shrink-0 xl:block">
          <RightRail />
        </div>
      </div>
      {queueOpen && (
        <div className="fixed inset-0 z-30 bg-black/50 xl:hidden" onClick={() => setQueueOpen(false)}>
          <div className="absolute right-0 top-0 h-[calc(100%-92px)] w-[min(100%,360px)]" onClick={(event) => event.stopPropagation()}>
            <RightRail onClose={() => setQueueOpen(false)} />
          </div>
        </div>
      )}
      <PlayerBar />
    </div>
  );
}

function Item({ to, label, icon: Icon }: { to: string; label: string; icon: LucideIcon }) {
  return (
    <NavLink
      to={to}
      end={to === "/"}
      className={({ isActive }) =>
        `flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition ${isActive ? "bg-white/[0.06] text-foam" : "text-mist hover:bg-white/[0.04] hover:text-foam"}`
      }
    >
      <Icon size={16} />
      {label}
    </NavLink>
  );
}
