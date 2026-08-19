import { useEffect, useState } from "react";
import { AlertTriangle, Check, Trash2, ShieldAlert } from "lucide-react";
import { api, connectLiveUpdates } from "../api.js";
import { SEVERITY_LABELS, formatDateTime, mediaUrl } from "../format.js";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
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
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

const SEVERITY_VARIANT = {
  critical: "danger",
  warning: "secondary",
  info: "success",
};

/** Turns a module's payload into one readable line. */
function describe(detail) {
  if (!detail) return "—";
  const parts = [];
  if (detail.plate) parts.push(`پلاک: ${detail.plate}`);
  if (detail.people != null) parts.push(`${detail.people} نفر`);
  if (detail.motion_percent != null) parts.push(`شدت حرکت ${detail.motion_percent}٪`);
  if (detail.changed_percent != null) parts.push(`تغییر ${detail.changed_percent}٪`);
  if (detail.minutes != null) parts.push(`${detail.minutes} دقیقه`);
  if (detail.still_for_seconds != null) parts.push(`${detail.still_for_seconds} ثانیه بی‌حرکت`);
  return parts.length ? parts.join(" · ") : "—";
}

export default function Alerts() {
  const [mode, setMode] = useState("open");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  async function load() {
    try {
      setRows(await api.alerts(mode === "open" ? { unacknowledged: true } : {}));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setLoading(true);
    load();
    const timer = setInterval(load, 30000);
    // A new alert should land on the screen without anyone refreshing.
    const disconnect = connectLiveUpdates((message) => {
      if (message.type === "alert") setRows((prev) => [message.payload, ...prev]);
    });
    return () => {
      clearInterval(timer);
      disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  async function acknowledge(id) {
    await api.acknowledgeAlert(id);
    load();
  }

  async function remove(id) {
    if (!window.confirm("این هشدار حذف شود؟")) return;
    await api.deleteAlert(id);
    load();
  }

  return (
    <>
      <PageHeader title="هشدارها" description="رویدادهایی که ماژول‌های تحلیل تصویر گزارش کرده‌اند">
        <Tabs value={mode} onValueChange={setMode}>
          <TabsList>
            <TabsTrigger value="open">
              <ShieldAlert className="size-4" />
              رسیدگی‌نشده
            </TabsTrigger>
            <TabsTrigger value="all">همه</TabsTrigger>
          </TabsList>
        </Tabs>
      </PageHeader>

      {error && <div className="text-destructive mb-4">{error}</div>}

      <Card className="overflow-hidden">
        <CardContent className="p-0">
          {loading ? (
            <div className="grid gap-2 p-4">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12" />
              ))}
            </div>
          ) : rows.length === 0 ? (
            <div className="text-muted-foreground p-10 text-center text-sm">
              <AlertTriangle className="mx-auto mb-2 size-8 opacity-40" />
              {mode === "open" ? "هشدار رسیدگی‌نشده‌ای نیست." : "هنوز هشداری ثبت نشده است."}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>زمان</TableHead>
                  <TableHead>نوع</TableHead>
                  <TableHead>دوربین</TableHead>
                  <TableHead>جزئیات</TableHead>
                  <TableHead>تصویر</TableHead>
                  <TableHead>وضعیت</TableHead>
                  <TableHead className="w-24" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((alert) => (
                  <TableRow key={alert.id}>
                    <TableCell className="text-muted-foreground whitespace-nowrap">
                      {formatDateTime(alert.occurred_at)}
                    </TableCell>
                    <TableCell>
                      <Badge variant={SEVERITY_VARIANT[alert.severity] || "secondary"}>
                        {SEVERITY_LABELS[alert.severity] || alert.severity}
                      </Badge>
                      <div className="mt-1 text-xs">{alert.module_name || alert.module}</div>
                    </TableCell>
                    <TableCell>{alert.camera_name || "—"}</TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {describe(alert.detail)}
                    </TableCell>
                    <TableCell>
                      {mediaUrl(alert.image_path) ? (
                        <a href={mediaUrl(alert.image_path)} target="_blank" rel="noreferrer">
                          <img
                            src={mediaUrl(alert.image_path)}
                            alt=""
                            className="h-12 w-16 rounded object-cover"
                          />
                        </a>
                      ) : (
                        "—"
                      )}
                    </TableCell>
                    <TableCell>
                      {alert.acknowledged_at ? (
                        <span className="text-muted-foreground text-xs">
                          رسیدگی‌شده {formatDateTime(alert.acknowledged_at)}
                        </span>
                      ) : (
                        <Badge variant="danger">جدید</Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        {!alert.acknowledged_at && (
                          <Button variant="ghost" size="icon" onClick={() => acknowledge(alert.id)}>
                            <Check className="size-4" />
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="icon"
                          className="text-destructive"
                          onClick={() => remove(alert.id)}
                        >
                          <Trash2 className="size-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </>
  );
}
