// Tải MediaPipe Face Landmarker từ file cục bộ (public/mediapipe/), KHÔNG gọi CDN lúc chạy.
// Chuẩn bị file bằng `uv run python scripts/fetch_web_assets.py`.

import type { FaceLandmarker } from "@mediapipe/tasks-vision";

export const MEDIAPIPE_WASM_PATH = "/mediapipe/wasm";
export const MEDIAPIPE_MODEL_PATH = "/mediapipe/face_landmarker.task";

export type LandmarkerHandle = { landmarker: FaceLandmarker; delegate: "GPU" | "CPU" };

/** Thử GPU trước, lỗi thì lùi về CPU (GPU trên iOS Safari có thể không ổn định). */
export async function createLandmarker(): Promise<LandmarkerHandle> {
  const { FaceLandmarker, FilesetResolver } = await import("@mediapipe/tasks-vision");
  const fileset = await FilesetResolver.forVisionTasks(MEDIAPIPE_WASM_PATH);

  let lastError: unknown;
  for (const delegate of ["GPU", "CPU"] as const) {
    try {
      const landmarker = await FaceLandmarker.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: MEDIAPIPE_MODEL_PATH, delegate },
        runningMode: "VIDEO",
        numFaces: 1,
      });
      return { landmarker, delegate };
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError instanceof Error ? lastError : new Error("Không tải được MediaPipe");
}
