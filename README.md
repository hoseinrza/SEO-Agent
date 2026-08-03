# SEO-Agent

An intelligent SEO management agent that performs website audits, builds keyword databases,
analyzes competitors, and generates actionable SEO reports.

یک ناوگان ایجنت سئو برای Claude Code: یک **SEO Manager** که پروژه را می‌گرداند،
هشت **ساب‌ایجنت تخصصی**، و یک **بانک کیورد** که قوانینش با کد اجرا می‌شود، نه با توصیه.

## چه چیزی داخل مخزن است

```
.claude/agents/      ۹ ایجنت — مدیر + متخصص‌ها
.claude/skills/      دانش مشترک: روش audit، اسکیمای دیتابیس، قالب گزارش‌ها
scripts/seodb.py     CLI بانک کیورد (فقط stdlib پایتون)
projects/            هر پروژه یک بانک کیورد مستقل
tests/               تست‌های قوانین دیتابیس
CLAUDE.md            نقش پیش‌فرض و قوانین غیرقابل‌مذاکره
```

## ایجنت‌ها

| ایجنت | مسئولیت |
| --- | --- |
| `seo-manager` | مالک پروژه، Workflow شش‌مرحله‌ای، اولویت‌بندی، گزارش نهایی |
| `technical-seo-auditor` | crawl، index، redirect، CWV، schema، JS rendering + SEO Health Score |
| `onpage-seo-analyst` | title، meta، heading، intent match، internal link، خوانایی |
| `keyword-researcher` | کشف کیورد، search intent، clustering، topic map |
| `competitor-analyst` | کیوردهای مشترک/مفقود، content gap، الگوی رقبا |
| `content-strategist` | تقویم محتوا، brief نویسنده، ساختار مقاله، FAQ schema |
| `link-building-analyst` | کیفیت بک‌لینک، ریسک‌ها، فرصت‌های لینک، outreach |
| `keyword-db-manager` | نگهبان بانک کیورد و تاریخچه‌ی رتبه |
| `seo-reporter` | گزارش عملکرد، مانیتورینگ هفتگی، Roadmap |

Claude بر اساس درخواست، ایجنت مناسب را انتخاب می‌کند. می‌توانی صریح هم بگویی:
«با `technical-seo-auditor` سایت را بررسی کن».

## شروع سریع

```bash
# ۱. ساخت پروژه
python3 scripts/seodb.py --project projects/mysite init \
  --domain mysite.com --industry "فروشگاه آنلاین" \
  --audience "مخاطب هدف" --country IR --language fa

# ۲. ثبت کیورد (تکراری و هم‌املا را رد می‌کند)
python3 scripts/seodb.py --project projects/mysite kw add "خرید کفش ورزشی" \
  --intent Transactional --volume 3600 --difficulty 38 \
  --url /shoes --priority High --cluster "کفش ورزشی" --type Primary

# ۳. ثبت رتبه (تاریخچه حفظ می‌شود)
python3 scripts/seodb.py --project projects/mysite kw check "خرید کفش ورزشی" \
  --position 14 --url /shoes --source gsc

# ۴. اجرای قوانین دیتابیس
python3 scripts/seodb.py --project projects/mysite audit

# ۵. گزارش
python3 scripts/seodb.py --project projects/mysite report full --days 7 --out auto
python3 scripts/seodb.py --project projects/mysite report weekly --out auto
```

`projects/example-shop/` یک پروژه‌ی نمونه با داده‌ی واقعی‌نما، گزارش‌های تولیدشده و
یک مورد cannibalization برای دیدن خروجی‌هاست.

## بانک کیورد

هر کیورد این فیلدها را دارد: keyword، main topic، search intent، search volume،
keyword difficulty، CPC، competition level، current/target position، target URL،
content type، priority، status، last checked، cluster، keyword type، notes —
به‌علاوه‌ی تاریخچه‌ی کامل رتبه در فایل جدا.

قوانینی که **کد** اجرا می‌کند، نه حافظه‌ی مدل:

- کیورد تکراری ثبت نمی‌شود.
- تشابه املایی فارسی تشخیص داده می‌شود: «سایدبای‌ساید» = «ساید بای ساید»
  (نیم‌فاصله، ي/ی، ك/ک، اعراب، ارقام عربی).
- کیورد ثبت‌نشده قابل ردیابی نیست.
- تاریخچه‌ی رتبه فقط append می‌شود.
- URLی که در SERP رتبه گرفته، صفحه‌ی هدف را بی‌سروصدا عوض نمی‌کند — همین اختلاف،
  cannibalization را آشکار می‌کند.
- `audit` این‌ها را پیدا می‌کند: cannibalization زنده و بالقوه، صفحات بدون کیورد هدف،
  کیورد بدون URL، رتبه‌های قدیمی، کیورد بدون cluster، مقادیر نامعتبر.

## گزارش‌ها

```bash
report full        # SEO Performance Report کامل
report weekly      # مانیتورینگ هفتگی
report changes     # Gained / Lost / Improvements / Drops
report traffic     # لندینگ‌پیج‌ها، فرصت‌ها، صفحات رو به افت
report content     # صفحات موفق/ضعیف، content gap، نیازمند update
report competitors # مشترک / مفقود / فرصت محتوا
report roadmap     # سه افق: 0-7 روز، ۱-۳ ماه، ۳-۱۲ ماه
```

## تست

```bash
python3 -m unittest discover -s tests -v
```

بدون وابستگی خارجی — فقط کتابخانه‌ی استاندارد پایتون ۳.

## قواعد کیفیت

- هیچ توصیه‌ای بدون دلیل و بدون بررسی تاثیر تجاری.
- داده‌ی ساختگی ممنوع؛ ستون خالی از عدد جعلی بهتر است.
- قبل از حذف یا تغییر URL، هشدار صریح و نقشه‌ی 301.
- خروجی همیشه اولویت‌بندی‌شده و عملیاتی.
