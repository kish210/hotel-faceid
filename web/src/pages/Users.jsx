import { useEffect, useState } from "react";
import { KeyRound, Plus, Trash2, UserPlus } from "lucide-react";
import { api } from "../api.js";
import { formatDateTime } from "../format.js";
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

const ROLE_LABELS = {
  admin: "مدیر سیستم",
  manager: "مدیر",
  reception: "پذیرش",
  security: "حراست",
};

const EMPTY = {
  username: "",
  password: "",
  full_name: "",
  role: "reception",
  active: true,
};

export default function Users() {
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState(null);
  const [passwordBusy, setPasswordBusy] = useState(false);

  async function load() {
    try {
      setUsers(await api.users());
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function create(event) {
    event.preventDefault();
    try {
      await api.createUser(form);
      setForm(EMPTY);
      setOpen(false);
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function toggle(user, active) {
    await api.updateUser(user.id, { active });
    load();
  }

  async function remove(user) {
    if (!window.confirm(`کاربر «${user.username}» حذف شود؟`)) return;
    await api.deleteUser(user.id);
    load();
  }

  async function changePassword() {
    const current = window.prompt("رمز عبور فعلی را وارد کنید");
    if (current === null) return;
    const next = window.prompt("رمز عبور جدید (حداقل ۶ کاراکتر)");
    if (!next) return;
    setPasswordBusy(true);
    try {
      await api.changeOwnPassword({ current_password: current, new_password: next });
      window.alert("رمز عبور با موفقیت تغییر کرد.");
    } catch (err) {
      setError(err.message);
    } finally {
      setPasswordBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="مدیریت کاربران" description="مدیریت دسترسی پرسنل به پنل">
        <div className="flex gap-2">
          <Button variant="outline" onClick={changePassword} disabled={passwordBusy}>
            <KeyRound className="size-4" />
            تغییر رمز عبور من
          </Button>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button>
                <UserPlus className="size-4" />
                افزودن کاربر
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>افزودن کاربر جدید</DialogTitle>
                <DialogDescription>دسترسی نقش‌محور (RBAC) را تعیین کنید.</DialogDescription>
              </DialogHeader>
              <form onSubmit={create} className="grid gap-4">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="grid gap-1.5">
                    <Label>نام کاربری</Label>
                    <Input value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required />
                  </div>
                  <div className="grid gap-1.5">
                    <Label>رمز عبور (حداقل ۶ کاراکتر)</Label>
                    <Input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
                  </div>
                  <div className="grid gap-1.5">
                    <Label>نام کامل</Label>
                    <Input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
                  </div>
                  <div className="grid gap-1.5">
                    <Label>نقش</Label>
                    <select
                      value={form.role}
                      onChange={(e) => setForm({ ...form, role: e.target.value })}
                      className="bg-input border-input h-9 rounded-md border px-3 text-sm"
                    >
                      {Object.entries(ROLE_LABELS).map(([value, label]) => (
                        <option key={value} value={value}>{label}</option>
                      ))}
                    </select>
                  </div>
                </div>
                {error && <div className="text-destructive text-sm">{error}</div>}
                <DialogFooter>
                  <Button type="submit">ثبت کاربر</Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </PageHeader>

      {error && <div className="text-destructive mb-4">{error}</div>}

      <Card className="overflow-hidden">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>نام کاربری</TableHead>
                <TableHead>نام کامل</TableHead>
                <TableHead>نقش</TableHead>
                <TableHead>وضعیت</TableHead>
                <TableHead>ساخته‌شده در</TableHead>
                <TableHead className="w-40" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((user) => (
                <TableRow key={user.id}>
                  <TableCell className="font-medium">{user.username}</TableCell>
                  <TableCell>{user.full_name || "—"}</TableCell>
                  <TableCell>
                    <Badge variant="info">{ROLE_LABELS[user.role] || user.role}</Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <Switch
                        checked={user.active}
                        onCheckedChange={(checked) => toggle(user, checked)}
                      />
                      <span className="text-muted-foreground text-xs">
                        {user.active ? "فعال" : "غیرفعال"}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{formatDateTime(user.created_at)}</TableCell>
                  <TableCell>
                    <Button variant="ghost" size="icon" onClick={() => remove(user)} className="text-destructive">
                      <Trash2 className="size-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {users.length === 0 && (
                <TableRow>
                  <TableCell colSpan="6" className="text-muted-foreground py-10 text-center">
                    <Plus className="mx-auto mb-2 size-8 opacity-40" />
                    کاربری ثبت نشده است.
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
