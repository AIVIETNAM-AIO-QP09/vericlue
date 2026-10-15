// Chọn kịch bản mock qua `?scenario=...` để thử cả 4 nhánh với API mock.
// CHỈ hoạt động ngoài môi trường production: bản build không có (và API cũng chỉ nghe header này khi
// USE_MOCK_MODELS=true).

const SCENARIO_PATTERN = /^[a-z_]{1,32}$/;

/** Trả tên kịch bản từ chuỗi query, hoặc undefined nếu production / thiếu / sai dạng. */
export function resolveScenario(search: string, nodeEnv: string | undefined): string | undefined {
  if (nodeEnv === "production") return undefined;
  const value = new URLSearchParams(search).get("scenario");
  return value && SCENARIO_PATTERN.test(value) ? value : undefined;
}
