import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Save } from "lucide-react";
import { api } from "../api.js";
import { GENDER_LABELS, ROLE_LABELS, formatDate, formatDateTime, mediaUrl } from "../format.js";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Avatar, AvatarImage } from "@/components/ui/avatar";
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

function StatCard({ label, value, highlight }) {
  return (
    <Card className={highlight ? "border-primary/40" : ""}>
      <CardContent>
        <div className="text-muted-foreground text-sm">{label}</div>
        <div className="mt-1 text-2xl font-bold">{value}</div>
      </CardContent>
    </Card>
  );
}

export default function PersonDetail() {
  const { id } = useParams();
  const [person, setPerson] = useState(null);
  const [events, setEvents] = useState([]);
  const [stays, setStays] = useState([]);
  const [error, setError] = useState(null);
  const [draft, setDraft] = useState({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const [p, e, s] = await Promise.all([
          api.person(id),
          api.personEvents(id),
          api.personStays(id),
        ]);
        if (cancelled) return;
        setPerson(p);
        setEvents(e);
        setStays(s);
        setDraft({
          display_name: p.display_name || "",
          role: p.role,
          gender: p.gender || "unknown",
          room_number: p.room_number || "",
          phone: p.phone || "",
          alarm_enabled: !!p.alarm_enabled,
          alarm_note: p.alarm_note || "",
        });
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [id]);

  async function save() {
    setSaving(true);
    try {
      const updated = await api.updatePerson(id, draft);
      setPerson({ ...person, ...updated });
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  if (error) return <div className="text-destructive">{error}</div>;
  if (!person) {
    return (
      <div className="grid gap-4">
        <Skeleton className="h-10 w-64" />
        <div className="grid gap-4 lg:grid-cols-3">
          <Skeleton className="h-96" />
          <div className="grid gap-4 lg:col-span-2">
            <Skeleton className="h-28" />
            <Skeleton className="h-64" />
            <Skeleton className="h-64" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      <PageHeader
        title={person.display_name || "پروفایل فرد"}
        description={`شناسه یکتا: ${person.id}`}
      />

      <div className="grid items-start gap-4 lg:grid-cols-3">
        <Card className="overflow-hidden">
          <CardContent className="p-0">
            {mediaUrl(person.reference_image) ? (
              <img
                src={mediaUrl(person.reference_image)}
                alt=""
                className="aspect-square w-full object-cover"
              />
            ) : (
              <div className="bg-muted flex aspect-square items-center justify-center">
                <Avatar className="size-24 text-3xl">
                  <AvatarImage src="" />
                </Avatar>
              </div>
            )}
            <div className="grid gap-4 p-6">
              <div className="grid gap-2">
                <Label>نام</Label>
                <Input value={draft.display_name} onChange={(e) => setDraft({ ...draft, display_name: e.target.value })} />
              </div>
              <div className="grid gap-2">
                <Label>نقش</Label>
                <select
                  value={draft.role}
                  onChange={(e) => setDraft({ ...draft, role: e.target.value })}
                  className="bg-input border-input h-9 rounded-md border px-3 text-sm"
                >
                  {Object.entries(ROLE_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </div>
              <div className="grid gap-2">
                <Label>جنسیت</Label>
                <select
                  value={draft.gender}
                  onChange={(e) => setDraft({ ...draft, gender: e.target.value })}
                  className="bg-input border-input h-9 rounded-md border px-3 text-sm"
                >
                  {Object.entries(GENDER_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
                <p className="text-muted-foreground text-xs">
                  {person.gender_manual
                    ? "به‌صورت دستی تعیین شده است."
                    : "به‌صورت خودکار از روی تصویر تشخیص داده می‌شود؛ تغییر دستی جایگزین آن می‌شود."}
                </p>
              </div>
              <div className="grid gap-2">
                <Label>شماره اتاق</Label>
                <Input value={draft.room_number} onChange={(e) => setDraft({ ...draft, room_number: e.target.value })} />
              </div>
              <div className="grid gap-2">
                <Label>شماره تماس</Label>
                <Input value={draft.phone} onChange={(e) => setDraft({ ...draft, phone: e.target.value })} />
              </div>
              <div className="border-destructive/40 grid gap-2 rounded-md border p-3">
                <label className="flex items-center gap-2 text-sm font-medium">
                  <input
                    type="checkbox"
                    checked={!!draft.alarm_enabled}
                    onChange={(e) => setDraft({ ...draft, alarm_enabled: e.target.checked })}
                  />
                  فرد تحت نظر (هشدار هنگام تشخیص)
                </label>
                <p className="text-muted-foreground text-xs">
                  با هر بار شناسایی این فرد، هشدار برای پذیرش و حراست نمایش داده می‌شود.
                </p>
                {draft.alarm_enabled && (
                  <Input
                    placeholder="علت — مثلاً سابقهٔ سرقت، بدهی، ممنوع‌الورود"
                    value={draft.alarm_note || ""}
                    onChange={(e) => setDraft({ ...draft, alarm_note: e.target.value })}
                  />
                )}
              </div>

              <Button onClick={save} disabled={saving}>
                <Save className="size-4" />
                {saving ? "در حال ذخیره…" : "ذخیره تغییرات"}
              </Button>
            </div>
          </CardContent>
        </Card>

        <div className="grid gap-4 lg:col-span-2">
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <StatCard label="وضعیت" value={person.present ? "داخل هتل" : "خارج"} highlight={person.present} />
            <StatCard label="شب‌های اقامت فعلی" value={person.current_stay_nights} />
            <StatCard label="مجموع شب‌های اقامت" value={person.total_nights} />
            <StatCard
              label="جنسیت / سن تخمینی"
              value={`${GENDER_LABELS[person.gender] || GENDER_LABELS.unknown}${
                person.age_estimate ? ` · ${person.age_estimate} سال` : ""
              }`}
            />
            <StatCard label="اولین مشاهده" value={formatDate(person.first_seen_at)} />
          </div>

          <Card className="overflow-hidden">
            <CardHeader>
              <CardTitle className="text-base">سابقه اقامت</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ورود</TableHead>
                    <TableHead>خروج</TableHead>
                    <TableHead>تعداد شب</TableHead>
                    <TableHead>اتاق</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {stays.map((stay) => (
                    <TableRow key={stay.id}>
                      <TableCell className="text-muted-foreground">{formatDateTime(stay.checkin_at)}</TableCell>
                      <TableCell>
                        {stay.active ? (
                          <Badge variant="success">در حال اقامت</Badge>
                        ) : (
                          <span className="text-muted-foreground">{formatDateTime(stay.checkout_at)}</span>
                        )}
                      </TableCell>
                      <TableCell>{stay.nights}</TableCell>
                      <TableCell>{stay.room_number || "—"}</TableCell>
                    </TableRow>
                  ))}
                  {stays.length === 0 && (
                    <TableRow>
                      <TableCell colSpan="4" className="text-muted-foreground py-8 text-center">
                        سابقه‌ای ثبت نشده است.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <Card className="overflow-hidden">
            <CardHeader>
              <CardTitle className="text-base">تاریخچه تردد</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>زمان</TableHead>
                    <TableHead>نوع</TableHead>
                    <TableHead>اطمینان</TableHead>
                    <TableHead>تصویر</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {events.map((event) => (
                    <TableRow key={event.id}>
                      <TableCell className="text-muted-foreground whitespace-nowrap">{formatDateTime(event.occurred_at)}</TableCell>
                      <TableCell>
                        <Badge variant={event.direction === "in" ? "success" : "danger"}>
                          {event.direction === "in" ? "ورود" : "خروج"}
                          {event.manual ? " (دستی)" : ""}
                        </Badge>
                      </TableCell>
                      <TableCell>{event.confidence ? `${Math.round(event.confidence * 100)}٪` : "—"}</TableCell>
                      <TableCell>
                        {mediaUrl(event.image_path) ? (
                          <Avatar className="size-8">
                            <AvatarImage src={mediaUrl(event.image_path)} alt="" />
                          </Avatar>
                        ) : (
                          "—"
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                  {events.length === 0 && (
                    <TableRow>
                      <TableCell colSpan="4" className="text-muted-foreground py-8 text-center">
                        ترددی ثبت نشده است.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
