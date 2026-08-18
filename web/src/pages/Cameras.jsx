import { useEffect, useState } from "react";
import { Plus, Trash2, Video, VideoOff, Camera } from "lucide-react";
import { api, connectLiveUpdates } from "../api.js";
import { PURPOSE_LABELS, formatDateTime } from "../format.js";
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
  DialogTrigger,
} from "@/components/ui/dialog";

const EMPTY = {
  name: "",
  brand: "hikvision",
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

const BRANDS = {
  hikvision: "Hikvision",
  dahua: "Dahua",
  onvif: "ONVIF (عمومی)",
};

export default function Cameras() {
  const [cameras, setCameras] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState(null);

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

  async function create(event) {
    event.preventDefault();
    try {
      await api.createCamera({ ...form, port: Number(form.port) });
      setForm(EMPTY);
      setOpen(false);
      load();
    } catch (err) {
      setError(err.message);
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
          value={form[key]}
          onChange={(e) => setForm({ ...form, [key]: e.target.value })}
        />
      </div>
    );
  }

  return (
    <>
      <PageHeader title="مدیریت دوربین‌ها" description="افزودن و پایش دوربین‌های تحت شبکه">
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="size-4" />
              افزودن دوربین
            </Button>
          </DialogTrigger>
          <DialogContent className="max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>افزودن دوربین جدید</DialogTitle>
              <DialogDescription>مشخصات اتصال دوربین تحت شبکه را وارد کنید.</DialogDescription>
            </DialogHeader>
            <form onSubmit={create} className="grid gap-4">
              <div className="grid gap-3 sm:grid-cols-2">
                {field("name", "نام دوربین")}
                <div className="grid gap-1.5">
                  <Label>برند</Label>
                  <select
                    value={form.brand}
                    onChange={(e) => setForm({ ...form, brand: e.target.value })}
                    className="bg-input border-input h-9 rounded-md border px-3 text-sm"
                  >
                    {Object.entries(BRANDS).map(([value, label]) => (
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
                {field("password", "رمز عبور دوربین", "password")}
                {field("rtsp_url", "آدرس RTSP (اختیاری)")}
              </div>
              <div className="flex items-center gap-2">
                <Switch
                  id="device-engine"
                  checked={form.use_device_face_engine}
                  onCheckedChange={(checked) => setForm({ ...form, use_device_face_engine: checked })}
                />
                <Label htmlFor="device-engine">استفاده از موتور تشخیص چهره داخلی دوربین</Label>
              </div>
              {error && <div className="text-destructive text-sm">{error}</div>}
              <DialogFooter>
                <Button type="submit">ثبت دوربین</Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </PageHeader>

      {error && <div className="text-destructive mb-4">{error}</div>}

      <Card className="overflow-hidden">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>نام</TableHead>
                <TableHead>برند</TableHead>
                <TableHead>نقش</TableHead>
                <TableHead>محل</TableHead>
                <TableHead>آدرس</TableHead>
                <TableHead>وضعیت</TableHead>
                <TableHead>آخرین ارتباط</TableHead>
                <TableHead className="w-20" />
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
                  <TableCell>{camera.brand}</TableCell>
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
                    <Button variant="ghost" size="icon" onClick={() => remove(camera.id)} className="text-destructive">
                      <Trash2 className="size-4" />
                    </Button>
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
