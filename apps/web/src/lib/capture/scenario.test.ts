import { describe, expect, it } from "vitest";

import { resolveScenario } from "./scenario";

describe("resolveScenario", () => {
  it("development đọc được kịch bản", () => {
    expect(resolveScenario("?scenario=low_quality", "development")).toBe("low_quality");
  });

  it("test cũng được", () => {
    expect(resolveScenario("?scenario=low_quality", "test")).toBe("low_quality");
  });

  it("production luôn undefined dù có query hợp lệ", () => {
    expect(resolveScenario("?scenario=low_quality", "production")).toBeUndefined();
  });

  it("env undefined hoạt động như dev", () => {
    expect(resolveScenario("?scenario=review", undefined)).toBe("review");
  });

  it("chấp nhận chuỗi không có dấu ?", () => {
    expect(resolveScenario("scenario=pass", "development")).toBe("pass");
  });

  it("đọc được khi có query khác đi kèm", () => {
    expect(resolveScenario("?a=1&scenario=voice&b=2", "development")).toBe("voice");
  });

  it("thiếu query thì undefined", () => {
    expect(resolveScenario("", "development")).toBeUndefined();
    expect(resolveScenario("?", "development")).toBeUndefined();
  });

  it("query không liên quan thì undefined", () => {
    expect(resolveScenario("?mode=low_quality", "development")).toBeUndefined();
  });

  it.each([
    ["chữ hoa", "?scenario=Low_Quality"],
    ["có khoảng trắng", "?scenario=a b"],
    ["đường dẫn", "?scenario=../x"],
    ["quá 32 ký tự", `?scenario=${"a".repeat(33)}`],
    ["rỗng", "?scenario="],
    ["có số", "?scenario=case1"],
    ["có dấu gạch ngang", "?scenario=low-quality"],
  ])("giá trị sai dạng (%s) thì undefined", (_name, search) => {
    expect(resolveScenario(search, "development")).toBeUndefined();
  });

  it("đúng 32 ký tự thì chấp nhận", () => {
    const name = "a".repeat(32);
    expect(resolveScenario(`?scenario=${name}`, "development")).toBe(name);
  });
});
