import { useEffect, useState } from "react";
import { Boxes, Download, Loader2, Trash2, CheckCircle2 } from "lucide-react";
import { api } from "../api.js";
import { CPU_COST_LABELS } from "../format.js";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";

const COST_VARIANT = { light: "success", moderate: "secondary", heavy: "danger" };

export default function Modules() {
  const [modules, setModules] = useState(null);
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [sourceUrl, setSourceUrl] = useState("");

  async function load() {
    try {
      setModules(await api.analyticsModules());
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function install(id) {
    setBusy(id);
    setError(null);
    setNotice(null);
    try {
      await api.installModule(id, sourceUrl ? { source_url: sourceUrl } : {});
      setNotice("ماژول با موفقیت نصب شد.");
      setSourceUrl("");
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(null);
    }
  }

  async function remove(id) {
    if (!window.confirm("فایل‌های این ماژول حذف شوند؟ دوربین‌ها تنظیماتشان را نگه می‌دارند.")) return;
    setBusy(id);
    try {
      await api.removeModule(id);
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(null);
    }
  }

  if (!modules) {
    return (
      <div className="grid gap-4">
        <Skeleton className="h-10 w-64" />
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-40" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <>
      <PageHeader
        title="ماژول‌های تحلیل تصویر"
        description="قابلیت‌هایی که می‌توانید روی هر دوربین فعال کنید"
      />

      {error && <div className="text-destructive mb-4">{error}</div>}
      {notice && <div className="mb-4 text-emerald-500">{notice}</div>}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {modules.map((module) => (
          <Card key={module.id} className={module.installed ? "" : "border-dashed"}>
            <CardContent className="grid gap-3">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="font-semibold">{module.name}</div>
                  <div className="text-muted-foreground text-xs">
                    نسخه {module.version} · شناسه <span dir="ltr">{module.id}</span>
                  </div>
                </div>
                {module.installed ? (
                  <Badge variant="success">
                    <CheckCircle2 className="size-3" />
                    آماده
                  </Badge>
                ) : (
                  <Badge variant="secondary">نصب‌نشده</Badge>
                )}
              </div>

              <p className="text-muted-foreground text-sm leading-6">{module.description}</p>

              <div className="flex flex-wrap items-center gap-2 text-xs">
                <Badge variant={COST_VARIANT[module.cpu_cost] || "secondary"}>
                  بار پردازشی: {CPU_COST_LABELS[module.cpu_cost] || module.cpu_cost}
                </Badge>
                <span className="text-muted-foreground">
                  روی {module.cameras} دوربین فعال است
                </span>
                {module.needs_pack && module.pack_size_mb && (
                  <span className="text-muted-foreground">
                    حجم بسته: {module.pack_size_mb} مگابایت
                  </span>
                )}
              </div>

              {module.needs_pack ? (
                <div className="flex items-center gap-2">
                  <Button
                    variant={module.installed ? "outline" : "default"}
                    size="sm"
                    disabled={busy === module.id}
                    onClick={() => install(module.id)}
                  >
                    {busy === module.id ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : (
                      <Download className="size-4" />
                    )}
                    {module.installed ? "به‌روزرسانی" : "نصب ماژول"}
                  </Button>
                  {module.installed && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="text-destructive"
                      disabled={busy === module.id}
                      onClick={() => remove(module.id)}
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  )}
                </div>
              ) : (
                <div className="text-muted-foreground flex items-center gap-2 text-xs">
                  <Boxes className="size-4" />
                  همراه سامانه نصب است — فقط در صفحهٔ دوربین‌ها فعالش کنید.
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <Card className="mt-4">
        <CardContent className="grid gap-2">
          <Label>نصب از روی فایل (اختیاری)</Label>
          <p className="text-muted-foreground text-xs">
            اگر سرور به اینترنت دسترسی ندارد، فایل بستهٔ ماژول را روی همین سیستم کپی کنید و
            مسیر کاملش را اینجا بنویسید، سپس دکمهٔ «نصب ماژول» را بزنید.
          </p>
          <Input
            dir="ltr"
            placeholder="C:\HotelFaceID\anpr-1.0.zip"
            value={sourceUrl}
            onChange={(event) => setSourceUrl(event.target.value)}
          />
        </CardContent>
      </Card>
    </>
  );
}
