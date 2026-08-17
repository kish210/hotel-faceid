import { useEffect, useState } from "react";
import { ScrollText } from "lucide-react";
import { api } from "../api.js";
import { formatDateTime } from "../format.js";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const ACTION_LABELS = {
  "auth.login": "ورود به سامانه",
  "auth.login_failed": "ورود ناموفق",
  "user.change_password": "تغییر رمز عبور",
  "person.update": "بروزرسانی پروفایل فرد",
  "person.merge": "ادغام دو شناسه",
  "person.forget": "حذف کامل اطلاعات فرد",
  "camera.create": "افزودن دوربین",
  "camera.update": "ویرایش دوربین",
  "camera.delete": "حذف دوربین",
  "user.create": "افزودن کاربر",
  "user.update": "ویرایش کاربر",
  "user.delete": "حذف کاربر",
  "face_search": "جست‌وجوی تصویری",
};

const ACTION_VARIANT = {
  "auth.login_failed": "danger",
  "person.forget": "warning",
  "camera.delete": "danger",
  "user.delete": "danger",
  "auth.login": "success",
  "face_search": "info",
};

export default function Audit() {
  const [rows, setRows] = useState([]);
  const [error, setError] = useState(null);
  const [actionFilter, setActionFilter] = useState("");

  async function load() {
    try {
      setRows(await api.audit({ ...(actionFilter && { action: actionFilter }), limit: 200 }));
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    load();
  }, [actionFilter]);

  return (
    <>
      <PageHeader title="گزارش عملیات (Audit Log)" description="ردگیری همه دسترسی‌ها و اقدامات اپراتورها">
        <select
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          className="bg-input border-input h-9 rounded-md border px-3 text-sm"
        >
          <option value="">همه عملیات‌ها</option>
          {Object.entries(ACTION_LABELS).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </PageHeader>

      {error && <div className="text-destructive mb-4">{error}</div>}

      <Card className="overflow-hidden">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>زمان</TableHead>
                <TableHead>عملیات</TableHead>
                <TableHead>کاربر</TableHead>
                <TableHead>جزئیات</TableHead>
                <TableHead>آدرس IP</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                <TableRow key={row.id}>
                  <TableCell className="text-muted-foreground whitespace-nowrap">{formatDateTime(row.created_at)}</TableCell>
                  <TableCell>
                    <Badge variant={ACTION_VARIANT[row.action] || "secondary"}>
                      {ACTION_LABELS[row.action] || row.action}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono text-xs">{row.user_id ? row.user_id.slice(0, 8) : "—"}</TableCell>
                  <TableCell className="text-muted-foreground font-mono text-xs">
                    {row.detail ? JSON.stringify(row.detail) : "—"}
                  </TableCell>
                  <TableCell className="font-mono text-xs" dir="ltr">{row.ip_address || "—"}</TableCell>
                </TableRow>
              ))}
              {rows.length === 0 && (
                <TableRow>
                  <TableCell colSpan="5" className="text-muted-foreground py-10 text-center">
                    <ScrollText className="mx-auto mb-2 size-8 opacity-40" />
                    عملیاتی ثبت نشده است.
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
