import { useEffect, useState } from "react";
import { Plus, Trash2, Video, VideoOff, Camera, Pencil, ScanSearch, Loader2 } from "lucide-react";
import { api, connectLiveUpdates } from "../api.js";
import { BRAND_LABELS, PURPOSE_LABELS, formatDateTime } from "../format.js";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const EMPTY = {
  name: "",
  brand: "onvif",
  model: "",
  firmware: "",
  serial_number: "",
  purpose: "entry",
  location: "",
  host: "",
  port: 80,
  rtsp_url: "",
  username: "",
  password: "",
  use_device_face_engine: false,
  enabled: true,
};

/** Strips the fields the API does not accept on write. */
function toForm(camera) {
  return {
    ...EMPTY,
    ...Object.fromEntries(
      Object.keys(EMPTY).map((key) => [key, camera[key] ?? EMPTY[key]])
    ),
    password: "", // never round-trips: left blank means "keep the stored one"
  };
}

export default function Cameras() {
  const [cameras, setCameras] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [editing, setEditing] = useState(null); // camera id, or null when adding
  const [open, setOpen] = useState(false);
  const [error, setError] = useState(null);
  const [probing, setProbing] = useState(false);
  const [probeResult, setProbeResult] = useState(null);

  async function load() {
    try {
      setCameras(await api.cameras());
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    load();
    const timer = setInterval(load, 30000);
    const disconnect = connectLiveUpdates((message) => {
      if (message.type === "camera-status") {
        setCameras((prev) =>
          prev.map((camera) =>
            camera.id === message.payload.camera_id
              ? {
                  ...camera,
                  online: message.payload.online,
                  last_seen_at: message.payload.last_seen_at,
                }
              : camera
          )
        );
      }
    });
    return () => {
      clearInterval(timer);
      disconnect();
    };
  }, []);

  function openCreate() {
    setForm(EMPTY);
    setEditing(null);
    setProbeResult(null);
    setError(null);
    setOpen(true);
  }

  function openEdit(camera) {
    setForm(toForm(camera));
    setEditing(camera.id);
    setProbeResult(null);
    setError(null);
    setOpen(true);
  }

  async function submit(event) {
    event.preventDefault();
    setError(null);
    try {
      const body = { ...form, port: Number(form.port) };
      if (editing) {
        // An empty password field must not wipe the stored credential.
        if (!body.password) delete body.password;
        await api.updateCamera(editing, body);
      } else {
        await api.createCamera(body);
      }
      setOpen(false);
      setForm(EMPTY);
      setEditing(null);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function detect() {
    if (!form.host) {
      setError("ابتدا آدرس IP دوربین را وارد کنید");
      return;
    }
    setProbing(true);
    setProbeResult(null);
    setError(null);
    try {
      const result = await api.probeCamera({
        host: form.host,
        port: Number(form.port) || 80,
        username: form.username || null,
        password: form.password || null,
        camera_id: editing,
      });
      setProbeResult(result);
      if (result.detected) {
        setForm((prev) => ({
          ...prev,
          brand: result.brand,
          model: result.model || prev.model,
          firmware: result.firmware || prev.firmware,
          serial_number: result.serial_number || prev.serial_number,
          name: prev.name || result.model || prev.name,
        }));
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setProbing(false);
    }
  }

  async function remove(id) {
    if (!window.confirm("این دوربین حذف شود؟")) return;
    await api.deleteCamera(id);
    load();
  }

  function field(key, label, type = "text") {
    return (
      <div className="grid gap-1.5">
        <Label>{label}</Label>
        <Input
          type={type}
          value={form[key] ?? ""}
          onChange={(e) => setForm({ ...form, [key]: e.target.value })}
        />
      </div>
    );
  }

  return (
    <>
      <PageHeader title="مدیریت دوربین‌ها" description="افزودن، ویرایش و پایش دوربین‌های تحت شبکه">
        <Button onClick={openCreate}>
          <Plus className="size-4" />
          افزودن دوربین
        </Button>
      </PageHeader>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editing ? "ویرایش دوربین" : "افزودن دوربین جدید"}</DialogTitle>
            <DialogDescription>
              مشخصات اتصال دوربین را وارد کنید یا با «تشخیص خودکار» از خود دستگاه بخوانید.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={submit} className="grid gap-4">
            <div className="grid gap-3 sm:grid-cols-2">
              {field("name", "نام دوربین")}
              <div className="grid gap-1.5">
                <Label>برند</Label>
                <select
                  value={form.brand}
                  onChange={(e) => setForm({ ...form, brand: e.target.value })}
                  className="bg-input border-input h-9 rounded-md border px-3 text-sm"
                >
                  {Object.entries(BRAND_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </div>
              <div className="grid gap-1.5">
                <Label>نقش دوربین</Label>
                <select
                  value={form.purpose}
                  onChange={(e) => setForm({ ...form, purpose: e.target.value })}
                  className="bg-input border-input h-9 rounded-md border px-3 text-sm"
                >
                  {Object.entries(PURPOSE_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </div>
              {field("location", "محل نصب")}
              {field("host", "آدرس IP")}
              {field("port", "پورت", "number")}
              {field("username", "نام کاربری دوربین")}
              {field(
                "password",
                editing ? "رمز عبور (خالی = بدون تغییر)" : "رمز عبور دوربین",
                "password"
              )}
              {field("model", "مدل دستگاه")}
              {field("rtsp_url", "آدرس RTSP (اختیاری)")}
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <Button type="button" variant="outline" onClick={detect} disabled={probing}>
                {probing ? <Loader2 className="size-4 animate-spin" /> : <ScanSearch className="size-4" />}
                {probing ? "در حال شناسایی…" : "تشخیص خودکار مدل دوربین"}
              </Button>
              {probeResult?.detected && (
                <span className="text-muted-foreground text-sm">
                  {BRAND_LABELS[probeResult.brand] || probeResult.brand}
                  {probeResult.model ? ` — ${probeResult.model}` : ""}
                  {probeResult.firmware ? ` (نسخه ${probeResult.firmware})` : ""}
                </span>
              )}
              {probeResult && !probeResult.detected && (
                <span className="text-destructive text-sm">{probeResult.detail}</span>
              )}
            </div>

            {probeResult?.detected && probeResult.supports_device_face_engine && (
              <div className="text-muted-foreground text-xs">
                این مدل موتور تشخیص چهره داخلی دارد — می‌توانید گزینهٔ زیر را روشن کنید.
              </div>
            )}

            <div className="flex items-center gap-2">
              <Switch
                id="device-engine"
                checked={form.use_device_face_engine}
                onCheckedChange={(checked) => setForm({ ...form, use_device_face_engine: checked })}
              />
              <Label htmlFor="device-engine">استفاده از موتور تشخیص چهره داخلی دوربین</Label>
            </div>
            <div className="flex items-center gap-2">
              <Switch
                id="camera-enabled"
                checked={form.enabled}
                onCheckedChange={(checked) => setForm({ ...form, enabled: checked })}
              />
              <Label htmlFor="camera-enabled">دوربین فعال باشد</Label>
            </div>

            {error && <div className="text-destructive text-sm">{error}</div>}
            <DialogFooter>
              <Button type="submit">{editing ? "ذخیره تغییرات" : "ثبت دوربین"}</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {error && !open && <div className="text-destructive mb-4">{error}</div>}

      <Card className="overflow-hidden">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>نام</TableHead>
                <TableHead>برند / مدل</TableHead>
                <TableHead>نقش</TableHead>
                <TableHead>محل</TableHead>
                <TableHead>آدرس</TableHead>
                <TableHead>وضعیت</TableHead>
                <TableHead>آخرین ارتباط</TableHead>
                <TableHead className="w-24" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {cameras.map((camera) => (
                <TableRow key={camera.id}>
                  <TableCell className="font-medium">
                    <span className="flex items-center gap-2">
                      {camera.online ? <Video className="text-emerald-500 size-4" /> : <VideoOff className="text-muted-foreground size-4" />}
                      {camera.name}
                    </span>
                  </TableCell>
                  <TableCell>
                    <div>{BRAND_LABELS[camera.brand] || camera.brand}</div>
                    {camera.model && (
                      <div className="text-muted-foreground text-xs" dir="ltr">{camera.model}</div>
                    )}
                  </TableCell>
                  <TableCell>{PURPOSE_LABELS[camera.purpose] || camera.purpose}</TableCell>
                  <TableCell>{camera.location || "—"}</TableCell>
                  <TableCell className="font-mono text-xs" dir="ltr">{camera.host}:{camera.port}</TableCell>
                  <TableCell>
                    <Badge variant={camera.online ? "success" : "secondary"}>
                      {camera.online ? "آنلاین" : "آفلاین"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{formatDateTime(camera.last_seen_at)}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      <Button variant="ghost" size="icon" onClick={() => openEdit(camera)}>
                        <Pencil className="size-4" />
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => remove(camera.id)} className="text-destructive">
                        <Trash2 className="size-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {cameras.length === 0 && (
                <TableRow>
                  <TableCell colSpan="8" className="text-muted-foreground py-10 text-center">
                    <Camera className="mx-auto mb-2 size-8 opacity-40" />
                    هنوز دوربینی ثبت نشده است.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </>
  );
}
