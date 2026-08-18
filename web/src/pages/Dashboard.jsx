import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Users,
  UserCheck,
  Mars,
  Venus,
  Briefcase,
  BedDouble,
  LogIn,
  LogOut,
  Video,
  TrendingUp,
} from "lucide-react";
import { api, connectLiveUpdates } from "../api.js";
import { formatTime } from "../format.js";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

function Stat({ icon: Icon, label, value, highlight }) {
  return (
    <Card className={highlight ? "border-primary/40" : ""}>
      <CardContent className="flex items-center justify-between gap-3">
        <div>
          <div className="text-muted-foreground text-sm">{label}</div>
          <div className="mt-1 text-3xl font-bold tracking-tight">{value}</div>
        </div>
        <div className={highlight ? "bg-primary/15 text-primary" : "bg-muted text-muted-foreground"}>
          <div className="flex size-11 items-center justify-center rounded-xl">
            <Icon className="size-5" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [occupancy, setOccupancy] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const result = await api.dashboard();
        if (!cancelled) {
          setData(result);
          setOccupancy(result.occupancy);
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    }

    load();
    const timer = setInterval(load, 60000);
    const disconnect = connectLiveUpdates((message) => {
      if (message.type === "occupancy") setOccupancy(message.payload);
    });

    return () => {
      cancelled = true;
      clearInterval(timer);
      disconnect();
    };
  }, []);

  if (error) return <div className="text-destructive">{error}</div>;
  if (!data) {
    return (
      <div className="grid gap-4">
        <Skeleton className="h-10 w-64" />
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
        <Skeleton className="h-80" />
      </div>
    );
  }

  const chartData = data.last_24h.map((bucket) => ({
    hour: formatTime(bucket.hour),
    ورود: bucket.entries,
    خروج: bucket.exits,
  }));

  return (
    <>
      <PageHeader title="داشبورد لحظه‌ای" description="نمای زنده از وضعیت حضور مهمانان و تردد">
        <div className="flex items-center gap-2 text-sm">
          <span className="relative flex size-2.5">
            <span className="bg-emerald-500 absolute inline-flex size-full animate-ping rounded-full opacity-75" />
            <span className="bg-emerald-500 relative inline-flex size-2.5 rounded-full" />
          </span>
          <span className="text-muted-foreground">زنده</span>
        </div>
      </PageHeader>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat icon={Users} label="نفرات حاضر در هتل" value={occupancy?.total ?? 0} highlight />
        <Stat icon={UserCheck} label="مهمانان حاضر" value={occupancy?.guests ?? 0} />
        <Stat icon={Briefcase} label="کارکنان حاضر" value={occupancy?.staff ?? 0} />
        <Stat icon={Mars} label="آقایان حاضر" value={occupancy?.males ?? 0} />
        <Stat icon={Venus} label="بانوان حاضر" value={occupancy?.females ?? 0} />
        <Stat icon={BedDouble} label="اقامت‌های فعال" value={data.active_stays} />
        <Stat icon={LogIn} label="ورود امروز" value={data.today_entries} />
        <Stat icon={LogOut} label="خروج امروز" value={data.today_exits} />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-4">
        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <TrendingUp className="size-4" />
              تردد ۲۴ ساعت اخیر
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis dataKey="hour" tick={{ fill: "currentColor" }} className="text-muted-foreground text-xs" />
                <YAxis tick={{ fill: "currentColor" }} className="text-muted-foreground text-xs" allowDecimals={false} />
                <Tooltip
                  contentStyle={{
                    background: "var(--popover)",
                    border: "1px solid var(--border)",
                    borderRadius: 8,
                    color: "var(--foreground)",
                  }}
                />
                <Legend />
                <Bar dataKey="ورود" fill="var(--chart-2)" radius={[4, 4, 0, 0]} />
                <Bar dataKey="خروج" fill="var(--destructive)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Video className="size-4" />
              وضعیت دوربین‌ها
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground text-sm">آنلاین</span>
              <span className="text-2xl font-bold">{data.cameras_online}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground text-sm">کل دوربین‌ها</span>
              <span className="text-2xl font-bold">{data.cameras_total}</span>
            </div>
            <div className="bg-muted/50 h-2 overflow-hidden rounded-full">
              <div
                className="bg-emerald-500 h-full rounded-full transition-all"
                style={{
                  width: data.cameras_total
                    ? `${(data.cameras_online / data.cameras_total) * 100}%`
                    : "0%",
                }}
              />
            </div>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
