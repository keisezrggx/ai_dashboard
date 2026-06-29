import { NavLink } from "react-router-dom";
import { LayoutDashboard, PieChart, FlaskConical, Bot, Mic, Activity, PhoneCall } from "lucide-react";

const navItems = [
  { name: "Dashboard", path: "/", icon: <LayoutDashboard size={20} /> },
  { name: "Overview", path: "/overview", icon: <PieChart size={20} /> },
  { name: "Sampling", path: "/sampling", icon: <FlaskConical size={20} /> },
  { name: "Agent Sample", path: "/agent-sample", icon: <Bot size={20} /> },
  { name: "Audio Sample", path: "/audio-sample", icon: <Mic size={20} /> },
  { name: "Performance", path: "/performance", icon: <Activity size={20} /> },
  { name: "Hotline Calibration", path: "/hotline-calibration", icon: <PhoneCall size={20} /> },
];

export default function Sidebar() {
  return (
    <aside className="w-64 bg-white border-r border-gray-200 shadow-sm flex flex-col">
      <div className="p-6 border-b border-gray-100 flex items-center justify-between">
        <h1 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-indigo-600">
          AI Dashboard
        </h1>
      </div>
      <nav className="flex-1 p-4 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 ${
                isActive
                  ? "bg-blue-50 text-blue-700 font-medium shadow-sm shadow-blue-100"
                  : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
              }`
            }
          >
            {item.icon}
            <span>{item.name}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
