import { describe, expect, it } from "vitest";
import { unpackBytes } from "./data";

describe("unpackBytes", () => {
  it("décode les tableaux base64 du pipeline", () => {
    // np.array([1.5, nan], "<f4") et np.array([0x8826, 1], "<u8")
    const f = new Float32Array(unpackBytes({ dtype: "<f4", length: 2, base64: "AADAPwAAwH8=" }));
    expect(f[0]).toBe(1.5);
    expect(Number.isNaN(f[1])).toBe(true);
    const u = new BigUint64Array(unpackBytes({ dtype: "<u8", length: 2, base64: "JogAAAAAAAABAAAAAAAAAA==" }));
    expect(u[0].toString(16)).toBe("8826");
    expect(u[1]).toBe(1n);
  });
  it("refuse un tableau tronqué", () => {
    expect(() => unpackBytes({ dtype: "<f4", length: 3, base64: "AADAPwAAwH8=" })).toThrow();
  });
});
