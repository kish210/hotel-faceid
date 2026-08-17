import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Hotel, Lock, User } from "lucide-react";
import { api, setToken } from "../api.js";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await api.login(username, password);
      setToken(result.access_token);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="bg-background grid min-h-screen place-items-center p-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <div className="bg-primary text-primary-foreground mx-auto flex size-12 items-center justify-center rounded-xl">
            <Hotel className="size-6" />
          </div>
          <CardTitle className="mt-2">ورود به پنل مدیریت</CardTitle>
          <CardDescription>سامانه تشخیص چهره و مدیریت تردد هتل</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="username">نام کاربری</Label>
              <div className="relative">
                <User className="text-muted-foreground absolute top-1/2 right-3 size-4 -translate-y-1/2" />
                <Input
                  id="username"
                  placeholder="نام کاربری"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoFocus
                  className="pr-9"
                />
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="password">رمز عبور</Label>
              <div className="relative">
                <Lock className="text-muted-foreground absolute top-1/2 right-3 size-4 -translate-y-1/2" />
                <Input
                  id="password"
                  type="password"
                  placeholder="رمز عبور"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="pr-9"
                />
              </div>
            </div>
            {error && <div className="text-destructive text-sm">{error}</div>}
            <Button disabled={busy || !username || !password} className="w-full">
              {busy ? "در حال ورود…" : "ورود"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
