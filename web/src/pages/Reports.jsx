import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Download, FileDown, FileSpreadsheet } from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, getToken } from "../api.js";
import { formatDate, formatDateTime, mediaUrl } from "../format.js";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default function Reports() {
  const [daily, setDaily] = useState([]);
  const [top, setTop] = useState([]);
  const [at, setAt] = useState("");
  const [pointOccupancy, setPointOccupancy] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [d, t] = await Promise.all([api.dailyReport(), api.topGuests()]);
        setDaily(d);
        setTop(t);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function lookupOccupancy() {
    try {
      setPointOccupancy(await api.occupancy(new Date(at).toISOString()));
    } catch (err) {
      setError(err.message);
    }
  }

  async function download(path, filename) {
    const response = await fetch(path, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  }

  const chartData = daily.map((row) => ({
    day: formatDate(row.day),
    ورود: row.entries,
    خروج: row.exits,
    "میانگین اشغال": row.avg_occupancy,
  }));

  return (
    <>
      <PageHeader title="گزارش‌ها" description="گزارش‌های روزانه، لحظه‌ای و مهمانان وفادار" />

      {error && <div className="text-destructive mb-4">{error}</div>}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">اشغال هتل در یک لحظه مشخص</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3">
            <p className="text-muted-foreground text-sm">
              مثلاً برای پاسخ به «دیشب ساعت ۲۳ چند نفر در هتل بودند؟» تاریخ و ساعت را وارد کنید.
            </p>
            <Input type="datetime-local" value={at} onChange={(e) => setAt(e.target.value)} />
            <Button onClick={lookupOccupancy} disabled={!at}>
              محاسبه
            </Button>
            {pointOccupancy && (
              <div className="bg-muted/50 grid gap-2 rounded-lg p-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">مجموع</span>
                  <span className="font-bold">{pointOccupancy.total} نفر</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">مهمان</span>
                  <span>{pointOccupancy.guests}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">کارمند</span>
                  <span>{pointOccupancy.staff}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">بازدیدکننده</span>
                  <span>{pointOccupancy.visitors}</span>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle className="text-base">روند ۳۰ روز اخیر</CardTitle>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => download("/api/reports/daily.pdf", "daily-report.pdf")}>
                <FileDown className="size-4" />
                PDF
              </Button>
              <Button variant="outline" size="sm" onClick={() => download("/api/reports/daily.xlsx", "daily-report.xlsx")}>
                <FileSpreadsheet className="size-4" />
                Excel
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <Skeleton className="h-72" />
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                  <XAxis dataKey="day" tick={{ fill: "currentColor" }} className="text-muted-foreground text-xs" />
                  <YAxis tick={{ fill: "currentColor" }} className="text-muted-foreground text-xs" allowDecimals={false} />
                  <Tooltip
                    contentStyle={{
                      background: "var(--popover)",
                      border: "1px solid var(--border)",
                      borderRadius: 8,
                      color: "var(--foreground)",
                    }}
                  />
                  <Line type="monotone" dataKey="ورود" stroke="var(--chart-2)" dot={false} />
                  <Line type="monotone" dataKey="خروج" stroke="var(--destructive)" dot={false} />
                  <Line type="monotone" dataKey="میانگین اشغال" stroke="var(--chart-1)" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="mt-4 overflow-hidden">
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle className="text-base">مهمانان با بیشترین شب اقامت</CardTitle>
          <Button variant="outline" size="sm" onClick={() => download("/api/reports/top-guests.pdf", "top-guests.pdf")}>
            <Download className="size-4" />
            دریافت PDF
          </Button>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="grid gap-2 p-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-12" />
              ))}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>تصویر</TableHead>
                  <TableHead>نام</TableHead>
                  <TableHead>مجموع شب اقامت</TableHead>
                  <TableHead>تعداد مراجعه</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {top.map((row) => (
                  <TableRow key={row.person_id}>
                    <TableCell>
                      <Avatar>
                        <AvatarImage src={mediaUrl(row.reference_image)} alt="" />
                        <AvatarFallback className="text-xs">{(row.display_name || "؟").slice(0, 1)}</AvatarFallback>
                      </Avatar>
                    </TableCell>
                    <TableCell>
                      <Link to={`/persons/${row.person_id}`} className="font-medium hover:underline">
                        {row.display_name || <span className="text-muted-foreground">{row.person_id.slice(0, 8)}</span>}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Badge variant="success">{row.total_nights} شب</Badge>
                    </TableCell>
                    <TableCell>{row.visits}</TableCell>
                  </TableRow>
                ))}
                {top.length === 0 && (
                  <TableRow>
                    <TableCell colSpan="4" className="text-muted-foreground py-10 text-center">
                      داده‌ای برای نمایش وجود ندارد.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </>
  );
}
