const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
export async function fetchLatestLineup() {
    const today = new Date().toISOString().slice(0, 10);
    const r = await fetch(`${API_URL}/lineup/${today}`);
    if (r.status === 404)
        return null;
    if (!r.ok)
        throw new Error(`HTTP ${r.status}`);
    return (await r.json());
}
