"""Librosa feature extraction.

Only features the file actually supports are returned. Danceability and valence
are not inferred from audio. If librosa is not installed, callers get a clear
unavailable result.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np


def librosa_status() -> dict:
    try:
        import librosa  # noqa: F401
    except Exception as exc:  # pragma: no cover - depends on the environment
        return {"available": False, "detail": exc.__class__.__name__}
    import librosa

    return {"available": True, "version": librosa.__version__}


def extract_audio_file(path: Path) -> dict:
    """Extract tempo, energy, spectral, MFCC, and chroma features from a file."""
    status = librosa_status()
    if not status["available"]:
        raise RuntimeError("librosa is not installed, so audio files cannot be analyzed.")
    import librosa

    waveform, sample_rate = librosa.load(path, sr=22050, mono=True, duration=120)
    if waveform.size < sample_rate:
        raise ValueError("Audio is shorter than one second.")
    tempo, _beats = librosa.beat.beat_track(y=waveform, sr=sample_rate)
    tempo_value = float(np.atleast_1d(tempo)[0])
    rms = librosa.feature.rms(y=waveform)[0]
    centroid = librosa.feature.spectral_centroid(y=waveform, sr=sample_rate)[0]
    bandwidth = librosa.feature.spectral_bandwidth(y=waveform, sr=sample_rate)[0]
    rolloff = librosa.feature.spectral_rolloff(y=waveform, sr=sample_rate)[0]
    zcr = librosa.feature.zero_crossing_rate(waveform)[0]
    mfcc = librosa.feature.mfcc(y=waveform, sr=sample_rate, n_mfcc=13)
    chroma = librosa.feature.chroma_stft(y=waveform, sr=sample_rate)
    rms_mean = float(rms.mean())
    # RMS is turned into a 0-1 energy proxy with a fixed, documented scale.
    # It is named rms_energy so it is not confused with editorial "energy".
    rms_energy = float(np.clip(rms_mean / 0.12, 0.0, 1.0))
    return {
        "tempo": tempo_value,
        "rms_mean": rms_mean,
        "rms_energy": rms_energy,
        "spectral_centroid_mean": float(centroid.mean()),
        "spectral_bandwidth_mean": float(bandwidth.mean()),
        "spectral_rolloff_mean": float(rolloff.mean()),
        "zero_crossing_rate_mean": float(zcr.mean()),
        "mfcc_mean": [float(value) for value in mfcc.mean(axis=1)],
        "chroma_mean": [float(value) for value in chroma.mean(axis=1)],
        "duration_sec": float(len(waveform) / sample_rate),
        "sample_rate": int(sample_rate),
        "feature_source": "librosa",
        "not_estimated": ["danceability", "valence", "speechiness", "acousticness"],
    }
