const DEFAULT_TIMEOUT_MS = 10_000;

export async function fetchPublic(
  input: string,
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<Response> {
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    throw new RangeError("request timeout must be positive");
  }

  const controller = new AbortController();
  const timeout = globalThis.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(input, {
      cache: "no-store",
      signal: controller.signal,
    });
  } catch (error) {
    if (controller.signal.aborted) {
      throw new Error("Public data request timed out", { cause: error });
    }
    throw error;
  } finally {
    globalThis.clearTimeout(timeout);
  }
}
