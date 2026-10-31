import { TrackRow } from "../components/TrackRow";
import { usePlayer } from "../lib/store";

export function Liked() {
  const catalog = usePlayer((state) => state.catalog);
  const liked = usePlayer((state) => state.liked);
  const tracks = catalog.filter((track) => liked.includes(track.id));
  return (
    <div>
      <div className="text-[11px] uppercase tracking-[0.22em] text-mist">Liked songs</div>
      <h1 className="font-display mt-2 text-5xl">Saved on purpose.</h1>
      {tracks.length === 0 ? (
        <p className="mt-6 text-sm text-mist">No likes yet. A like is an explicit signal and moves artist, genre, and language affinity a small step.</p>
      ) : (
        <div className="mt-6">
          {tracks.map((track) => (
            <TrackRow key={track.id} track={track} queue={tracks} />
          ))}
        </div>
      )}
    </div>
  );
}
