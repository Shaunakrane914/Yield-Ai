import { NavLink } from "react-router-dom";

const navItems = [
  { to: "/setup", label: "Farm Setup" },
  { to: "/predict", label: "Yield Prediction" },
  { to: "/dashboard", label: "Dashboard" },
  { to: "/about", label: "About Us" },
];

export function Navbar() {
  return (
    <header className="topbar">
      <div className="brand">KrushiBandhu AI</div>
      <nav className="navlinks">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) => (isActive ? "navlink active" : "navlink")}
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </header>
  );
}
