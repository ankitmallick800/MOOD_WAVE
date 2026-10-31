# Training and evaluation

The demo is small enough to fit at process start. `backend/scripts/train.py` runs that same path and writes `backend/data/artifacts/train_summary.json` plus `popularity.joblib`.

```bash
cd backend
../.venv/bin/python scripts/train.py
../.venv/bin/python scripts/evaluate.py
```

`MOODWAVE_SEED` defaults to 42. NumPy, the synthetic generator, K-means, PCA, and TruncatedSVD all use that seed.

## What is fit

- Item-item cosine on the user-item matrix. Positive events add weight. Skips and dislikes subtract. The diagonal is zero so a track does not count as its own neighbor.
- Scores are passed through a logistic curve whose mean and scale come from training users, so the collaborative component sits on 0–1 before it is mixed with cosine.
- TruncatedSVD with up to 12 components. Known users score from their factors. The live listener, who is not in the matrix, uses a ridge fold-in after three positive tracks.
- Popularity is log-scaled positive mass from the same matrix.
- K-means on standardized energy, danceability, acousticness, valence, and normalized tempo. K is the maximum silhouette over k = 3..7.

## What is not fit on a click

Profile updates are an exponential moving average. Confidence is `n_positive / (n_positive + 8)`. Ranking blends onboarding with the inferred centroid at that rate. One like cannot replace the explicit profile.

## Evaluation protocol

`POST /api/ml/evaluate` and `scripts/evaluate.py` both call `app.ml.evaluate`.

- Cutoff is the 70th percentile of event timestamps.
- A listener needs at least four positive training tracks and two relevant test tracks they did not already touch.
- Relevance is like, complete, replay, and playlist add. NDCG uses grades 3, 2.5, 2, and 2.
- Profiles for evaluated listeners are rebuilt from training events only. The generator's hidden taste is not an input.
- Candidates exclude tracks seen in training.
- Item similarities include every training user, including the user being scored. Test events are excluded. That train-side inclusion is disclosed in the protocol payload.
- Default metrics use score order. Diversity reranking is what the player does. Pass `diversify: true` to measure the reranked lists instead.
- If fewer than eight listeners qualify, metrics are omitted and the warning says why. Numbers are not filled in.

## Weights

`POST /api/ml/config` stores hybrid weights, feature-group weights, diversity lambda, artist cap, and list length in SQLite. Group weights scale feature blocks by `sqrt(weight)` inside cosine. Raising `language` pulls the angle toward language agreement. It does not create a hard ban. A soft language factor still lowers tracks outside the listener's languages, and a higher discovery preference relaxes that factor.
