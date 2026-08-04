---
name: keyword-database
description: Schema, commands and rules for the project keyword bank (keywords, ranking history, clusters, pages, competitors) managed by scripts/seodb.py. Use when adding or updating keywords, recording ranking positions, building clusters, checking for duplicate or cannibalising keywords, or auditing keyword-database health.
---

# Keyword Database

بانک کیورد منبع حقیقت هر پروژه است. همه‌ی عملیات از `scripts/seodb.py` عبور می‌کند
تا قوانین توسط کد اجرا شوند، نه با یادآوری.

```bash
S="python3 scripts/seodb.py --project projects/<slug>"
```

## ساختار پروژه

```
projects/<slug>/
├── project.json          # domain, industry, audience, country, language, goals
├── keywords.csv          # بانک کیورد — یک سطر برای هر کیورد
├── ranking-history.csv   # تاریخچه‌ی رتبه — فقط append
├── clusters.csv          # دسته‌بندی کیوردها
├── pages.csv             # صفحات سایت
├── competitors.csv       # رتبه‌ی رقبا
└── reports/              # گزارش‌های تولیدشده
```

## اسکیمای `keywords.csv`

| ستون | توضیح | مقادیر مجاز |
| --- | --- | --- |
| `keyword` | خود کیورد | یکتا در هر پروژه |
| `main_topic` | موضوع اصلی | متن آزاد |
| `search_intent` | هدف جستجو | Informational, Commercial, Transactional, Navigational |
| `search_volume` | حجم جستجوی ماهانه | عدد (خالی اگر داده نداری) |
| `keyword_difficulty` | سختی | 0-100 |
| `cpc` | هزینه‌ی هر کلیک | عدد |
| `competition_level` | سطح رقابت | Low, Medium, High |
| `current_position` | رتبه‌ی فعلی | عدد، خالی = رتبه ندارد |
| `target_position` | رتبه‌ی هدف | عدد |
| `target_url` | URL هدف | مسیر یا URL کامل |
| `content_type` | نوع محتوا | متن آزاد (article, product, landing, ...) |
| `priority` | اولویت | High, Medium, Low |
| `status` | وضعیت | New, Planned, Writing, Published, Ranking, Improved |
| `last_checked` | آخرین بررسی | YYYY-MM-DD |
| `cluster` | نام cluster | باید در `clusters.csv` باشد |
| `keyword_type` | نقش در cluster | Primary, Secondary, Supporting, Long Tail, Question |
| `notes` | یادداشت | منبع داده را اینجا بنویس |

`$S help-fields` همین اسکیما را از خود کد چاپ می‌کند (منبع معتبر در صورت تغییر).

## چرخه‌ی حیات یک کیورد

```
New → Planned → Writing → Published → Ranking → Improved
```

`Ranking` و `Improved` به‌صورت خودکار توسط `kw check` تنظیم می‌شوند:

- ورود به SERP → `Ranking`
- رسیدن به بهترین رتبه‌ی تاریخی یا بهتر از آن → `Improved`
- افت به پایین‌تر از بهترین رتبه → بازگشت به `Ranking`

یعنی `Improved` وضعیت «الان در بهترین حالت تاریخی خود است» را نشان می‌دهد، نه یک برچسب
دائمی. کیوردی که افت کرده نباید `Improved` بماند — گزارش و Roadmap بر اساس همین وضعیت
تصمیم می‌گیرند.

## دستورهای پرکاربرد

```bash
# ساخت پروژه
$S init --domain example.com --industry "..." --audience "..." --country IR --language fa

# قبل از هر کیورد جدید: آیا مشابهش هست؟
$S kw search "خرید یخچال"

# ثبت کیورد
$S kw add "خرید یخچال ساید" --intent Transactional --volume 8100 --difficulty 42 \
  --url /product/side-by-side --priority High --cluster "یخچال ساید" --type Primary \
  --target-position 3 --notes "source: GSC export 1404-05"

# ثبت مشاهده‌ی رتبه (هم ردیف را به‌روز می‌کند هم تاریخچه را)
$S kw check "خرید یخچال ساید" --position 7 --url /product/side-by-side --source gsc

# افت کامل از SERP
$S kw check "خرید یخچال ساید" --position "" --note "dropped out"

# مشاهده
$S kw list --priority High --status Ranking
$S history --keyword "خرید یخچال ساید"
$S cluster list
```

## قوانین دیتابیس

1. **هیچ کیورد جدیدی بدون ثبت اضافه نشود.** کیوردی که فقط در گزارش هست، وجود ندارد.
2. **تغییرات رتبه ذخیره شود** — همیشه با `kw check`، هرگز با ویرایش دستی CSV.
3. **تاریخچه حفظ شود** — `ranking-history.csv` فقط append. حذف سطر تاریخی یعنی
   نابودکردن توانایی تشخیص افت رتبه.
4. **قبل از پیشنهاد محتوا، کیورد مشابه بررسی شود** — `kw search`.
5. **Cannibalization تشخیص داده شود** — `audit`.
6. **صفحات بدون کیورد هدف شناسایی شوند** — `audit`.

## محافظت‌های خودکار

CLI این‌ها را خودش جلو می‌گیرد:

- **کیورد تکراری** — ثبت دوباره رد می‌شود.
- **تشابه املایی** — «سایدبای‌ساید» و «ساید بای ساید» یکی شناخته می‌شوند
  (نرمال‌سازی فارسی: ي/ی، ك/ک، نیم‌فاصله، اعراب، ارقام عربی/فارسی).
- **کیورد نزدیک** — بالای آستانه‌ی تشابه هشدار می‌دهد و ثبت را متوقف می‌کند.
  `--force` فقط وقتی که واقعاً بتوانی توضیح دهی چرا دو صفحه‌ی جدا لازم است.
- **مقدار نامعتبر enum** — با پیام روشن رد می‌شود.
- **`kw check` روی کیورد ثبت‌نشده** — رد می‌شود (قانون ۱).
- **نوشتن هم‌زمان** — هر چرخه‌ی خواندن-تغییر-نوشتن زیر قفل `flock` روی همان جدول انجام
  می‌شود و نوشتن اتمیک است (فایل موقت + `os.replace`). پس وقتی چند ساب‌ایجنت موازی
  `kw add` می‌زنند، هیچ ردیفی گم نمی‌شود و فایل نیمه‌نوشته باقی نمی‌ماند. قفل به‌ازای هر
  جدول است، نه کل پروژه.
- **CSV injection** — مقداری که با `=`، `+`، `-` یا `@` شروع شود موقع نوشتن با `'` خنثی
  می‌شود تا Excel/Google Sheets آن را فرمول حساب نکند. این پیشوند فقط روی دیسک است؛
  خواندن، مقایسه و گزارش همان مقدار اصلی را می‌بینند — پس هرگز `'` را دستی به مقدارها اضافه نکن.

> کنار این‌ها، فایل‌های `*.csv.lock` در پوشه‌ی پروژه ساخته می‌شوند. این‌ها فقط قفل‌اند،
> داده نیستند؛ در `.gitignore` هستند و نباید commit یا ویرایش شوند.

## `audit` — یافته‌ها و معنایشان

```bash
$S audit --stale-days 30 --threshold 0.8
$S audit --strict          # exit code 1 اگر یافته‌ای باشد (برای CI)
```

| یافته | معنی |
| --- | --- |
| Exact duplicates | یک کیورد دو بار ثبت شده |
| Cannibalization `[live]` | یک کیورد با بیش از یک URL رتبه گرفته — مشکل امروز |
| Cannibalization `[planned]` | دو کیورد بسیار نزدیک با URLهای متفاوت — ریسک فردا |
| Near-duplicate | کیوردهای نزدیک روی یک URL — معمولاً سالم |
| Pages without target keyword | صفحه‌ای که هیچ کیوردی هدفش نگرفته |
| Live keywords without URL | کیورد منتشرشده بدون صفحه‌ی مشخص |
| Stale rankings | بیش از N روز چک نشده |
| Invalid field values | مقدار خارج از enum |

## گزارش‌ها

```bash
$S report full --days 7 --out auto
$S report weekly --days 7 --out auto
$S report changes|traffic|content|competitors|roadmap|keywords|overview
```

خروجی Markdown است و مستقیم در گزارش نهایی قابل درج.

## کیفیت داده

ستون خالی از عدد ساختگی بهتر است. اگر حجم جستجو یا KD واقعی نداری:
مقدار را خالی بگذار و در `notes` بنویس چه ابزاری لازم است. اولویت‌بندی مبتنی بر
داده‌ی جعلی، بودجه را به سمت اشتباه هدایت می‌کند.
