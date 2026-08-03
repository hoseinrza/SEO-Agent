---
name: seo-reporting
description: Templates and interpretation rules for SEO reports — the SEO Performance Report, weekly monitoring report, ranking-change analysis, traffic and content performance sections, competitor keyword report, and the three-horizon SEO roadmap. Use when producing any SEO report, weekly update, or roadmap from the keyword database.
---

# SEO Reporting

گزارش‌ها از دیتابیس ساخته می‌شوند، نه از حافظه. اول داده را بگیر، بعد تفسیر کن.

```bash
S="python3 scripts/seodb.py --project projects/<slug>"
$S report full --days 7 --out auto
$S report weekly --days 7 --out auto
```

## SEO Performance Report

```markdown
## SEO Performance Report

### Website Overview
- Domain / Industry / Target Audience / Current SEO Status

### Keyword Report
| Keyword | Position | Volume | Difficulty | URL | Status | Priority |

### Ranking Changes
- Keywords Gained / Keywords Lost / Position Improvements / Position Drops

### Traffic Analysis
- Organic Traffic Trend / Top Landing Pages / Traffic Opportunities / Declining Pages

### Technical SEO Report
- Crawl Issues / Index Issues / Speed Issues / Core Web Vitals / Mobile / Structured Data

### Content Performance Report
- صفحات موفق / صفحات ضعیف / Content Gap / نیازمند Update / محتواهای جدید پیشنهادی

### Competitor Keyword Report
- برای هر رقیب: Keywords Ranking / Missing / Shared / Content Opportunities

## SEO Roadmap
### Immediate Actions (0-7 Days)
### Short Term (1-3 Months)
### Long Term (3-12 Months)
```

## Weekly SEO Monitoring

```markdown
# Weekly SEO Monitoring — <domain> — <date>

## Summary
(۳ خط: مهم‌ترین برد، مهم‌ترین ریسک، تمرکز هفته‌ی آینده)

## رتبه‌های جدید
## افت رتبه‌ها          ← اولویت اول بررسی
## صفحات جدید
## مشکلات فنی جدید
## فرصت‌های جدید کیورد
## پیشنهاد اقدام بعدی   ← حداکثر ۵ مورد، با مالک
```

گزارش هفتگی باید در ۵ دقیقه خوانده شود. جدول طولانی را به فایل کامل ارجاع بده.

## تفسیر تغییرات رتبه

| مشاهده | فرضیه‌های محتمل | چطور تایید کنی |
| --- | --- | --- |
| افت ناگهانی یک کیورد | تغییر صفحه، cannibalization، رقیب جدید | `audit`، تاریخچه‌ی صفحه، SERP |
| افت هم‌زمان چند کیورد یک صفحه | مشکل فنی آن صفحه یا از دست رفتن لینک | index status، لاگ تغییرات |
| افت گسترده‌ی کل سایت | آپدیت الگوریتم یا مشکل سراسری فنی | تاریخ آپدیت‌ها، GSC coverage |
| نوسان ۳-۵ پله | نویز عادی SERP | چند هفته صبر — واکنش نشان نده |
| بهبود بدون اقدام ما | افت رقیب یا فصلی‌بودن | SERP رقبا، الگوی سال قبل |

نوسان کوچک را «نتیجه» گزارش نکن و برایش اقدام تجویز نکن. سیگنال را از نویز جدا کن.

## کیوردهای تازه‌ردیابی‌شده

کیوردی که اولین مشاهده‌اش داخل بازه‌ی گزارش است، مبنای مقایسه‌ی قبلی ندارد.
گزارش این‌ها را `newly tracked` علامت می‌زند — آن‌ها را به‌عنوان بهبود یا افت واقعی
گزارش نکن؛ فقط بگو تازه وارد ردیابی شده‌اند.

## Roadmap — منطق سه افق

| افق | چه چیزی اینجا می‌آید | معیار |
| --- | --- | --- |
| Immediate (0-7d) | cannibalization زنده، quick win رتبه ۴-۲۰ با KD پایین، صفحات بدون کیورد، مشکل Critical فنی | Impact بالا، Effort کم، ریسک پایین |
| Short Term (1-3m) | انتقال صفحه‌ی دو به صفحه‌ی یک، تولید محتوای در صف، رفع مشکلات High | نیازمند تولید یا توسعه |
| Long Term (3-12m) | تکمیل cluster، اعتبار موضوعی، لینک‌سازی، ممیزی دوره‌ای | استراتژیک، وابسته به زمان |

هر آیتم Roadmap باید داشته باشد: **کار مشخص، مالک، مهلت، معیار موفقیت.**
«بهبود محتوا» آیتم نیست. «بازنویسی H1 و افزودن جدول مقایسه به /product/x تا ۱۵ مهر،
هدف: ورود به تاپ ۱۰» آیتم است.

## قواعد نوشتن گزارش

- هر عدد باید منبع داشته باشد. عدد بدون منبع را حذف کن.
- داده‌ی موجود نیست ≠ داده صفر است. صریح بنویس «اندازه‌گیری نشده — نیازمند X».
- ترتیب گزارش = ترتیب اهمیت برای خواننده، نه ترتیب انجام کار توسط تو.
- یافته‌ی بحرانی (cannibalization زنده، افت شدید) در خلاصه‌ی بالای گزارش، نه در انتها.
- مسیر فایل گزارش را به کاربر بگو.
