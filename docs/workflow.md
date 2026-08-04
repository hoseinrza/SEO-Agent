# گردش کار پروژه‌ی سئو

راهنمای عملی اینکه ایجنت‌ها چطور با هم و با بانک کیورد کار می‌کنند.

## نمای کلی

```
کاربر
  │
  └── seo-manager ─────────── مالک پروژه، اولویت‌بندی، گزارش نهایی
         │
         │  ── تحلیل: مشکل را پیدا می‌کنند ──┐
         ├── seo-specialist                  │
         ├── search-specialist               │
         ├── competitive-analyst             │
         ├── performance-engineer            ├──► keyword-db-manager
         ├── accessibility-tester            │            │
         ├── data-analyst                    │            ▼
         ├── content-strategist              │      بانک کیورد
         ├── content-quality-editor          │   (تنها نویسنده‌ی دیتابیس)
         └── link-building-analyst ──────────┘            │
         │                                                │
         │  ── اصلاح: فقط با تایید کاربر ──                │
         ├── frontend-developer                           │
         ├── backend-developer                            │
         └── wordpress-master                             │
         │                                                ▼
         └── technical-writer ◄── knowledge-synthesizer ── می‌خواند از بانک
```

دو نکته‌ی کلیدی:

- **همه از یک منبع حقیقت می‌خوانند.** یافته‌ای که وارد بانک نشود، در گزارش هفته‌ی بعد
  وجود نخواهد داشت.
- **تحلیل و اصلاح جدا هستند.** ایجنت‌های توسعه فقط بعد از اینکه تحلیل مشکل را مشخص کرد و
  کاربر تایید کرد وارد می‌شوند — تغییر کد بر اساس حدس، بدتر از نبود تغییر است.

## مرحله ۱ — Intake

```bash
python3 scripts/seodb.py --project projects/<slug> init \
  --domain <domain> --industry "<industry>" --audience "<audience>" \
  --country <IR> --language <fa> --goals "<اهداف کسب‌وکار>"
```

بدون کشور و زبان هدف جلو نرو: SERP کشورهای مختلف متفاوت است و کل تحلیل کیورد
به آن وابسته است.

## مرحله ۲ — Technical Audit

`seo-specialist` را با دامنه و مسیر پروژه صدا بزن. خروجی:
لیست مشکلات با ساختار پنج‌جزئی + SEO Health Score.

صفحات کشف‌شده را ثبت کن تا بعداً بتوان صفحات بدون کیورد را پیدا کرد:

```bash
python3 scripts/seodb.py --project projects/<slug> page add <url> \
  --title "<title>" --page-type <product|blog|category> --traffic <n>
```

## مرحله ۳ — Keyword Research

`search-specialist` اول جستجو می‌کند، بعد ثبت:

```bash
S="python3 scripts/seodb.py --project projects/<slug>"
$S kw search "<term>"        # آیا مشابهش هست؟
$S cluster add "<cluster>" --page <url> --intent <intent> --structure "<outline>"
$S kw add "<keyword>" --intent <...> --cluster "<cluster>" --type Primary ...
```

اگر CLI ثبت را رد کرد، یعنی کیورد از قبل هست — آن را به همان cluster نگاشت کن،
نسخه‌ی دوم نساز.

## مرحله ۴ — Competitor Analysis

```bash
$S competitor add <competitor-domain> "<keyword>" --position <n> --volume <n> --url <url>
$S report competitors
```

کیوردهای missing که ارزش دارند را به `search-specialist` بده تا در بانک ثبت شوند.

## مرحله ۵ — Roadmap و Content Plan

```bash
$S audit                 # ورودی بخش Immediate Actions
$S report roadmap        # پیش‌نویس سه‌افقی از داده
```

`seo-manager` خروجی خودکار را بازبینی می‌کند: ترتیب را با Impact تجاری تنظیم می‌کند و
به هر آیتم مالک، مهلت و معیار موفقیت اضافه می‌کند.

`content-strategist` برای هر کیورد در صف، brief می‌نویسد و وضعیت را جلو می‌برد:

```bash
$S kw update "<kw>" --status Writing --url <target-url>
$S kw update "<kw>" --status Published
```

## مرحله ۶ — Weekly Monitoring

هر هفته:

```bash
# ۱. ثبت رتبه‌های جدید (برای هر کیورد ردیابی‌شده)
$S kw check "<kw>" --position <n> --url <ranking-url> --source gsc

# ۲. سلامت دیتابیس
$S audit

# ۳. گزارش
$S report weekly --days 7 --out auto
```

بعد `technical-writer` تفسیر می‌کند: چه شد، چرا، یعنی چه، حالا چه کنیم.

## چرخه‌ی وضعیت کیورد

```
New ──► Planned ──► Writing ──► Published ──► Ranking ⇄ Improved
                                                  │
                                                  └──► (افت کامل: position خالی)
```

`Ranking` و `Improved` خودکارند. `Improved` یعنی «الان در بهترین رتبه‌ی تاریخی خود است»؛
با افت، خودکار به `Ranking` برمی‌گردد.

## اشتباهات رایج

| اشتباه | چرا بد است | کار درست |
| --- | --- | --- |
| ویرایش دستی CSV | قوانین دور زده می‌شوند و تاریخچه خراب می‌شود | همیشه از CLI |
| `--force` برای عبور از هشدار تشابه | مسیر مستقیم به cannibalization | نگاشت به cluster موجود |
| پر کردن حجم جستجو با حدس | اولویت‌بندی را مسموم می‌کند | خالی بگذار + `volume: needed` |
| حذف سطر تاریخچه | تشخیص افت رتبه غیرممکن می‌شود | تاریخچه فقط append |
| گزارش نوسان ۲-۳ پله به‌عنوان نتیجه | نویز را سیگنال جا می‌زند | چند هفته صبر |
| پیشنهاد تغییر URL بدون هشدار | ریسک از دست رفتن ترافیک | هشدار + نقشه‌ی 301 |
