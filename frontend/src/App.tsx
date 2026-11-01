import { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { Shell } from "./layout/Shell";
import { usePlayer } from "./lib/store";
import { Discover } from "./pages/Discover";
import { ForYou } from "./pages/ForYou";
import { Library } from "./pages/Library";
import { Liked } from "./pages/Liked";
import { PlaylistGenerator } from "./pages/PlaylistGenerator";
import { ModelLab } from "./pages/ModelLab";
import { MoodStudio } from "./pages/MoodStudio";
import { Onboarding } from "./pages/Onboarding";
import { Settings } from "./pages/Settings";
import { Taste } from "./pages/Taste";

export function App() {
  const boot = usePlayer((state) => state.boot);
  const ready = usePlayer((state) => state.ready);
  const offline = usePlayer((state) => state.offline);
  const profile = usePlayer((state) => state.profile);
  const tick = usePlayer((state) => state.tick);

  useEffect(() => {
    void boot();
  }, [boot]);

  useEffect(() => {
    const id = window.setInterval(() => tick(), 200);
    return () => window.clearInterval(id);
  }, [tick]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT")) return;
      if (event.code === "Space") {
        event.preventDefault();
        void usePlayer.getState().toggle();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  if (!ready) {
    return <Screen title="Opening the catalog" body="Loading songs and your saved profile." />;
  }
  if (offline) {
    return (
      <Screen
        title="The ranker is not running."
        body={`${offline} Start the API on port 8000 if you are running it on this machine, then try again.`}
        actionLabel="Try again"
        onAction={() => void boot()}
      />
    );
  }

  const basename = import.meta.env.BASE_URL === "/" ? undefined : import.meta.env.BASE_URL.replace(/\/$/, "");

  return (
    <BrowserRouter basename={basename}>
      <Routes>
        <Route path="/onboarding" element={<Onboarding />} />
        <Route element={profile ? <Shell /> : <Navigate to="/onboarding" replace />}>
          <Route path="/" element={<ForYou />} />
          <Route path="/for-you" element={<Navigate to="/" replace />} />
          <Route path="/discover" element={<Discover />} />
          <Route path="/mood" element={<MoodStudio />} />
          <Route path="/lab" element={<ModelLab />} />
          <Route path="/playlist" element={<PlaylistGenerator />} />
          <Route path="/library" element={<Library />} />
          <Route path="/liked" element={<Liked />} />
          <Route path="/taste" element={<Taste />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
        <Route path="*" element={<Navigate to={profile ? "/" : "/onboarding"} replace />} />
      </Routes>
    </BrowserRouter>
  );
}

function Screen({ title, body, actionLabel, onAction }: { title: string; body: string; actionLabel?: string; onAction?: () => void }) {
  return (
    <div className="grid h-full place-items-center px-6">
      <div className="max-w-md">
        <div className="font-display text-4xl">{title}</div>
        <p className="mt-3 text-sm leading-6 text-mist">{body}</p>
        {actionLabel && onAction && (
          <button className="mt-5 rounded-full bg-foam px-4 py-2 text-sm text-ink" onClick={onAction}>
            {actionLabel}
          </button>
        )}
      </div>
    </div>
  );
}
