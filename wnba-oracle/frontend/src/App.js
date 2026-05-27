import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from "react";
import { LineupStack } from "./components/LineupStack";
import { fetchLatestLineup } from "./lib/api";
export function App() {
    const [lineup, setLineup] = useState(null);
    const [err, setErr] = useState(null);
    const [loading, setLoading] = useState(true);
    useEffect(() => {
        let cancelled = false;
        fetchLatestLineup()
            .then((data) => {
            if (!cancelled) {
                setLineup(data);
                setLoading(false);
            }
        })
            .catch((e) => {
            if (!cancelled) {
                setErr(e instanceof Error ? e.message : String(e));
                setLoading(false);
            }
        });
        return () => {
            cancelled = true;
        };
    }, []);
    return (_jsxs("main", { className: "app-shell", children: [_jsxs("header", { className: "app-header", children: [_jsxs("div", { children: [_jsxs("div", { className: "app-title", children: [_jsx("span", { children: "WNBA" }), " ", _jsx("span", { className: "app-title-accent", children: "Oracle" })] }), _jsx("div", { className: "slate-meta", children: lineup ? `slate ${lineup.slate_date}` : loading ? "loading…" : "—" })] }), lineup && (_jsx("span", { className: `entry-flag entry-flag--${lineup.entry_recommendation}`, children: lineup.entry_recommendation.replaceAll("_", " ") }))] }), err ? (_jsxs("div", { className: "error-state", children: [_jsx("strong", { children: "API unreachable." }), " ", err, ". Confirm ", _jsx("code", { children: "VITE_API_URL" }), " and that", " ", _jsx("code", { children: "/lineup" }), " has a frozen entry."] })) : loading ? (_jsx("div", { className: "placeholder", children: "contacting the oracle\u2026" })) : lineup ? (_jsx(LineupStack, { lineup: lineup })) : (_jsx("div", { className: "placeholder", children: "no frozen lineup for today yet" }))] }));
}
