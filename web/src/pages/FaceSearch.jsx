import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ImagePlus, Search, UserRound } from "lucide-react";
import { api } from "../api.js";
import { ROLE_LABELS, mediaUrl } from "../format.js";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default function FaceSearch() {
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef(null);

  function pickFile(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setPreview(URL.createObjectURL(file));
    setResult(null);
    setError(null);
    fileRef.current = file;
  }

  async function search() {
    if (!fileRef.current) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await api.faceSearch(fileRef.current));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="جست‌وجوی تصویری مهمان"
        description="عکس مهمان را آپلود کنید تا سامانه چهره او را با سوابق ثبت‌شده تطبیق دهد"
      />

      <Card className="max-w-2xl">
        <CardContent className="flex flex-col items-start gap-4 sm:flex-row sm:items-center">
          <label className="bg-muted flex cursor-pointer items-center gap-2 rounded-md border border-dashed px-4 py-2 text-sm hover:bg-accent">
            <ImagePlus className="size-4" />
            انتخاب عکس
            <input ref={fileRef} type="file" accept="image/*" onChange={pickFile} className="hidden" />
          </label>
          <Button onClick={search} disabled={busy || !fileRef.current}>
            <Search className="size-4" />
            {busy ? "در حال جست‌وجو…" : "جست‌وجو"}
          </Button>
          {preview && (
            <img
              src={preview}
              alt="پیش‌نمایش"
              className="size-24 rounded-xl border object-cover sm:ms-auto"
            />
          )}
        </CardContent>
      </Card>

      {error && <div className="text-destructive mt-4">{error}</div>}

      {result && (
        <Card className="mt-6 overflow-hidden">
          <CardContent className="p-0">
            {result.matches.length === 0 ? (
              <div className="text-muted-foreground p-10 text-center">
                <UserRound className="mx-auto mb-2 size-10 opacity-40" />
                مهمانی با این چهره در سوابق پیدا نشد.
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>تصویر</TableHead>
                    <TableHead>نام / شناسه</TableHead>
                    <TableHead>نقش</TableHead>
                    <TableHead>اتاق</TableHead>
                    <TableHead>شباهت</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {result.matches.map((match) => (
                    <TableRow key={match.person_id}>
                      <TableCell>
                        <Avatar>
                          <AvatarImage src={mediaUrl(match.reference_image)} alt="" />
                          <AvatarFallback className="text-xs">{(match.display_name || "؟").slice(0, 1)}</AvatarFallback>
                        </Avatar>
                      </TableCell>
                      <TableCell>
                        <Link to={`/persons/${match.person_id}`} className="font-medium hover:underline">
                          {match.display_name || <span className="text-muted-foreground">{match.person_id.slice(0, 8)}</span>}
                        </Link>
                      </TableCell>
                      <TableCell>{ROLE_LABELS[match.role] || match.role}</TableCell>
                      <TableCell>{match.room_number || "—"}</TableCell>
                      <TableCell>
                        <Badge variant={match.similarity > 0.6 ? "success" : "info"}>
                          {Math.round(match.similarity * 100)}٪
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}
    </>
  );
}
