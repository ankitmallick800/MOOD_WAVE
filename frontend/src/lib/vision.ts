const EXPRESSIONS = ["neutral", "happy", "sad", "angry", "fearful", "disgusted", "surprised"] as const;

export type Expression = (typeof EXPRESSIONS)[number];

type FaceApi = {
  nets: {
    tinyFaceDetector: { loadFromUri: (uri: string) => Promise<void> };
    faceExpressionNet: { loadFromUri: (uri: string) => Promise<void> };
  };
  TinyFaceDetectorOptions: new (options?: { inputSize?: number; scoreThreshold?: number }) => unknown;
  detectSingleFace: (
    input: HTMLVideoElement,
    options: unknown,
  ) => { withFaceExpressions: () => Promise<{ expressions: Record<string, number> } | undefined> };
};

let faceapi: FaceApi | null = null;
let loaded = false;

export async function loadExpressionModels(): Promise<void> {
  if (loaded) return;
  const module = (await import("@vladmandic/face-api")) as unknown as FaceApi;
  faceapi = module;
  await module.nets.tinyFaceDetector.loadFromUri("/models");
  await module.nets.faceExpressionNet.loadFromUri("/models");
  loaded = true;
}

export async function readExpression(video: HTMLVideoElement): Promise<Record<Expression, number> | null> {
  if (!faceapi || video.readyState < 2) return null;
  const options = new faceapi.TinyFaceDetectorOptions({ inputSize: 224, scoreThreshold: 0.45 });
  const detection = await faceapi.detectSingleFace(video, options).withFaceExpressions();
  if (!detection) return null;
  const output = {} as Record<Expression, number>;
  for (const key of EXPRESSIONS) output[key] = detection.expressions[key] ?? 0;
  return output;
}

export function smoothDistribution(
  previous: Record<string, number>,
  next: Record<string, number>,
  alpha = 0.35,
): Record<string, number> {
  const keys = Object.keys(next);
  const mixed: Record<string, number> = {};
  for (const key of keys) {
    const prior = previous[key] ?? next[key];
    mixed[key] = prior * (1 - alpha) + next[key] * alpha;
  }
  const total = Object.values(mixed).reduce((sum, value) => sum + value, 0) || 1;
  for (const key of keys) mixed[key] = mixed[key] / total;
  return mixed;
}

export function topExpression(distribution: Record<string, number>): { label: string; confidence: number } {
  let label = "neutral";
  let confidence = 0;
  for (const [key, value] of Object.entries(distribution)) {
    if (value > confidence) {
      label = key;
      confidence = value;
    }
  }
  return { label, confidence };
}
