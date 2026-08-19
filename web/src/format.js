const dateTime = new Intl.DateTimeFormat("fa-IR", {
  dateStyle: "short",
  timeStyle: "short",
});

const dateOnly = new Intl.DateTimeFormat("fa-IR", { dateStyle: "medium" });
const timeOnly = new Intl.DateTimeFormat("fa-IR", { timeStyle: "short" });

export function formatDateTime(value) {
  return value ? dateTime.format(new Date(value)) : "—";
}

export function formatDate(value) {
  return value ? dateOnly.format(new Date(value)) : "—";
}

export function formatTime(value) {
  return value ? timeOnly.format(new Date(value)) : "—";
}

export const ROLE_LABELS = {
  guest: "مهمان",
  staff: "کارمند",
  visitor: "بازدیدکننده",
  unknown: "نامشخص",
};

export const GENDER_LABELS = {
  male: "مرد",
  female: "زن",
  unknown: "نامشخص",
};

export const BRAND_LABELS = {
  hikvision: "Hikvision",
  dahua: "Dahua",
  axis: "Axis",
  foscam: "Foscam",
  onvif: "ONVIF (عمومی)",
  generic: "سایر",
};

export const SEVERITY_LABELS = {
  info: "اطلاع",
  warning: "هشدار",
  critical: "بحرانی",
};

export const CPU_COST_LABELS = {
  light: "سبک",
  moderate: "متوسط",
  heavy: "سنگین",
};

export const PURPOSE_LABELS = {
  entry: "ورودی",
  exit: "خروجی",
  bidirectional: "دوطرفه",
  monitor: "پایش",
};

export function mediaUrl(path) {
  return path ? `/media/${path}` : null;
}
