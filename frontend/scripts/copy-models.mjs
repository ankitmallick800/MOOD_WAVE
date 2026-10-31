import { copyFile, mkdir } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";

const require = createRequire(import.meta.url);
const modelDir = join(dirname(require.resolve("@vladmandic/face-api/package.json")), "model");
const target = join(process.cwd(), "public", "models");
const files = [
  "tiny_face_detector_model-weights_manifest.json",
  "tiny_face_detector_model.bin",
  "face_expression_model-weights_manifest.json",
  "face_expression_model.bin",
];

await mkdir(target, { recursive: true });
for (const file of files) {
  await copyFile(join(modelDir, file), join(target, file));
  console.log(`copied ${file}`);
}
