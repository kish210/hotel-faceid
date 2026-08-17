import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  Users,
  Search,
  Camera,
  FileBarChart,
  UserCog,
  ScrollText,
  LogOut,
  Hotel,
} from "lucide-react";
import { clearToken } from "./api.js";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { useEffect, useState } from "react";
import { api } from "./api.js";

const NAV = [
  { to: "/", label: "داشبورد", icon: LayoutDashboard, end: true },
  { to: "/guests", label: "مهمانان", icon: Users },
  { to: "/face-search", label: "جست‌وجوی تصویری", icon: Search },
  { to: "/cameras", label: "دوربین‌ها", icon: Camera },
  { to: "/reports", label: "گزارش‌ها", icon: FileBarChart },
  { to: "/users", label: "کاربران", icon: UserCog },
  { to: "/audit", label: "گزارش عملیات", icon: ScrollText },
];

export default function App() {
  const navigate = useNavigate();
  const [me, setMe] = useState(null);

  useEffect(() => {
    api.me().then(setMe).catch(() => {});
  }, []);

  function logout() {
    clearToken();
    navigate("/login", { replace: true });
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="flex min-h-screen">
        <aside className="bg-card sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-l p-4 lg:flex">
          <div className="flex items-center gap-3 px-2 py-3">
            <div className="bg-primary text-primary-foreground flex size-9 items-center justify-center rounded-lg">
              <Hotel className="size-5" />
            </div>
            <div>
              <div className="text-sm font-bold">سامانه تردد هوشمند</div>
              <div className="text-muted-foreground text-xs">مدیریت ورود/خروج هتل</div>
            </div>
          </div>
          <Separator className="my-4" />
          <nav className="flex flex-1 flex-col gap-1">
            {NAV.map(({ to, label, icon: Icon, end }) => (
              <NavLink key={to} to={to} end={end}>
                {({ isActive }) => (
                  <span
                    className={cn(
                      "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                      isActive
                        ? "bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                    )}
                  >
                    <Icon className="size-4" />
                    {label}
                  </span>
                )}
              </NavLink>
            ))}
          </nav>
          <Separator className="my-4" />
          <div className="flex items-center gap-3 px-2">
            <Avatar className="size-8">
              <AvatarFallback className="text-xs">{(me?.full_name || me?.username || "؟")?.slice(0, 1)}</AvatarFallback>
            </Avatar>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium">{me?.full_name || me?.username}</div>
              <div className="text-muted-foreground text-xs">{me?.role}</div>
            </div>
            <Button variant="ghost" size="icon" onClick={logout} title="خروج">
              <LogOut className="size-4" />
            </Button>
          </div>
        </aside>

        <div className="flex flex-1 flex-col">
          <header className="bg-card/50 sticky top-0 z-30 flex items-center justify-between border-b px-4 py-3 lg:hidden">
            <div className="flex items-center gap-2 font-bold">
              <Hotel className="size-5" />
              سامانه تردد هوشمند
            </div>
            <Button variant="ghost" size="icon" onClick={logout} title="خروج">
              <LogOut className="size-4" />
            </Button>
          </header>

          <main className="flex-1 overflow-x-auto p-4 md:p-8">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}
