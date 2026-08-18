import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Search, Users } from "lucide-react";
import { api } from "../api.js";
import { GENDER_LABELS, ROLE_LABELS, formatDateTime, mediaUrl } from "../format.js";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function Guests() {
  const [mode, setMode] = useState("present");
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    async function load() {
      try {
        const data =
          mode === "present"
            ? await api.present()
            : await api.persons({ ...(query && { q: query }), limit: 100 });
        if (!cancelled) setRows(data);
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [mode, query]);

  return (
    <>
      <PageHeader title="مهمانان" description="افراد حاضر در هتل و سوابق ثبت‌شده">
        <Tabs value={mode} onValueChange={setMode}>
          <TabsList>
            <TabsTrigger value="present">
              <Users className="size-4" />
              حاضر در هتل
            </TabsTrigger>
            <TabsTrigger value="all">همه افراد</TabsTrigger>
          </TabsList>
        </Tabs>
      </PageHeader>

      {mode === "all" && (
        <div className="relative mb-4 max-w-sm">
          <Search className="text-muted-foreground absolute top-1/2 right-3 size-4 -translate-y-1/2" />
          <Input
            placeholder="جست‌وجو بر اساس نام یا شماره اتاق"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="pr-9"
          />
        </div>
      )}

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
            <div className="text-muted-foreground p-8 text-center text-sm">
              {mode === "present" ? "هیچ‌کس در حال حاضر در هتل نیست." : "موردی یافت نشد."}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>تصویر</TableHead>
                  <TableHead>شناسه / نام</TableHead>
                  <TableHead>نقش</TableHead>
                  <TableHead>جنسیت</TableHead>
                  <TableHead>اتاق</TableHead>
                  <TableHead>{mode === "present" ? "زمان ورود" : "آخرین مشاهده"}</TableHead>
                  <TableHead>شب اقامت</TableHead>
                  <TableHead>وضعیت</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => {
                  const id = row.person_id || row.id;
                  return (
                    <TableRow key={id}>
                      <TableCell>
                        <Avatar>
                          <AvatarImage src={mediaUrl(row.reference_image)} alt="" />
                          <AvatarFallback className="text-xs">{(row.display_name || "؟").slice(0, 1)}</AvatarFallback>
                        </Avatar>
                      </TableCell>
                      <TableCell>
                        <Link to={`/persons/${id}`} className="font-medium hover:underline">
                          {row.display_name || <span className="text-muted-foreground">{id.slice(0, 8)}</span>}
                        </Link>
                      </TableCell>
                      <TableCell>{ROLE_LABELS[row.role] || row.role}</TableCell>
                      <TableCell>{GENDER_LABELS[row.gender] || GENDER_LABELS.unknown}</TableCell>
                      <TableCell>{row.room_number || "—"}</TableCell>
                      <TableCell className="text-muted-foreground">
                        {formatDateTime(row.first_entry || row.last_seen_at)}
                      </TableCell>
                      <TableCell>{row.nights ?? "—"}</TableCell>
                      <TableCell>
                        <Badge variant={row.present ? "success" : "secondary"}>
                          {row.present ? "داخل هتل" : "خارج"}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <div className="mt-4 text-right">
        <Button variant="outline" asChild>
          <Link to="/face-search">جست‌وجوی تصویری مهمان</Link>
        </Button>
      </div>
    </>
  );
}
