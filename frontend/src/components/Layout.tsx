import { NavLink, Outlet } from "react-router-dom";
import { useState } from "react";
import GlobalFilters from "./GlobalFilters";
import type { ApiFilters } from "../api/types";

const NAV_ITEMS = [
  { to: "/overview", label: "Overview" },
  { to: "/ai-impact", label: "AI Impact" },
  { to: "/ai-quality", label: "AI Quality" },
];

export default function Layout() {
  const [filters, setFilters] = useState<ApiFilters>({});

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <nav className="w-56 bg-gray-900 border-r border-gray-800 flex flex-col">
        <div className="p-4 border-b border-gray-800">
          <h1 className="text-sm font-semibold text-gray-300 tracking-wide uppercase">
            AI Codegen Dashboard
          </h1>
        </div>
        <ul className="flex-1 py-2">
          {NAV_ITEMS.map(({ to, label }) => (
            <li key={to}>
              <NavLink
                to={to}
                className={({ isActive }) =>
                  `block px-4 py-2 text-sm ${
                    isActive
                      ? "bg-gray-800 text-white font-medium border-l-2 border-brand-500"
                      : "text-gray-400 hover:text-gray-200 hover:bg-gray-800/50"
                  }`
                }
              >
                {label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="bg-gray-900 border-b border-gray-800 px-6 py-3 flex items-center justify-between">
          <GlobalFilters filters={filters} onChange={setFilters} />
        </header>
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet context={{ filters }} />
        </main>
      </div>
    </div>
  );
}
