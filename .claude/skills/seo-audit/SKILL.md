---
name: seo-audit
description: Method and scoring rubric for a full SEO audit — the six-step project workflow, the reproducible 0-100 SEO Health Score, the five-part issue format (what/why/impact/fix/priority), and the standard SEO Analysis Report template. Use when running a site audit, scoring SEO health, prioritising SEO issues, or producing an SEO analysis report.
---

# SEO Audit Method

## Workflow شش‌مرحله‌ای

| مرحله | کار | ایجنت |
| --- | --- | --- |
| 1 | Intake: URL، حوزه، کشور، زبان، رقبا، اهداف | `seo-manager` |
| 2 | Technical Audit | `technical-seo-auditor` |
| 3 | Keyword Research + Clustering | `keyword-researcher` |
| 4 | Competitor Analysis | `competitor-analyst` |
| 5 | SEO Roadmap + Content Plan | `seo-manager`، `content-strategist` |
| 6 | Weekly Monitoring | `seo-reporter` |

مرحله‌ی ۱ اختیاری نیست. کشور و زبان هدف، SERP را عوض می‌کنند؛ تحلیل بدون آن‌ها بی‌اعتبار است.

## SEO Health Score (0-100)

امتیاز باید **قابل بازتولید** باشد. شش دسته، هرکدام از سقف خود شروع می‌کند و بابت
هر مشکل کسر می‌شود؛ کف هر دسته صفر است.

| دسته | سقف | چه چیزی را می‌سنجد |
| --- | --- | --- |
| Indexability & Crawl | 25 | robots، sitemap، ایندکس، canonical، redirect |
| Speed & Core Web Vitals | 20 | LCP، INP، CLS، TTFB |
| On-page & Content | 20 | title، meta، heading، intent match، عمق محتوا |
| Architecture & Internal linking | 15 | عمق کلیک، orphan، anchor، ساختار URL |
| Structured data | 10 | وجود و اعتبار schema |
| Mobile & UX | 10 | viewport، برابری محتوا، تجربه‌ی لمسی |

کسر بابت هر مشکل: **Critical −۱۰، High −۵، Medium −۲، Low −۱**

قواعد:

- جدول امتیاز را همراه دلیل هر کسر نشان بده تا عدد قابل بحث باشد.
- دسته‌ای که نتوانستی اندازه بگیری، امتیاز کامل نگیرد؛ آن را `not measured`
  علامت بزن و از مخرج کم کن (مثلاً «۶۲ از ۸۰ سنجیده‌شده»).
- امتیاز، ابزار ارتباط است نه هدف. هرگز برای بهترشدن عدد، مشکل واقعی را نادیده نگیر.

## طبقه‌بندی اولویت

| اولویت | تعریف | نمونه |
| --- | --- | --- |
| **Critical** | مانع خزش/ایندکس یا افت درآمد فعال | `noindex` روی صفحه‌ی محصول، سایت down، robots سایت را بلاک کرده |
| **High** | اثر مستقیم و بزرگ بر رتبه یا ترافیک | intent mismatch در صفحه‌ی پول‌ساز، LCP بالای ۴ ثانیه، cannibalization زنده |
| **Medium** | اثر معنادار ولی نه فوری | meta تکراری، schema ناقص، لینک داخلی ضعیف |
| **Low** | بهبود تدریجی | alt تصاویر فرعی، بهینه‌سازی جزئی متن |

مرتب‌سازی نهایی با **Impact × Confidence ÷ Effort** — نه صرفاً با شدت.
مشکل Critical که رفعش سه ماه طول می‌کشد، در Immediate Actions نمی‌آید؛
در Roadmap با مالک و مهلت می‌آید.

## قالب هر مشکل

```markdown
#### <عنوان>
- **مشکل چیست؟** <توصیف + شواهد/URL>
- **چرا مهم است؟** <مکانیزم اثر>
- **تاثیر احتمالی؟** <کمّی با بازه>
- **روش حل؟** <گام‌های عملی>
- **اولویت:** Critical | High | Medium | Low
```

بدون هر پنج جزء، یافته ناقص است. «چرا مهم است» را با کلیشه پر نکن —
توضیح بده که این مشکل دقیقاً روی *این* سایت چه می‌کند.

## قالب گزارش تحلیلی

```markdown
# SEO Analysis Report
## Overview
## Critical Issues
## Technical SEO
## On Page SEO
## Keyword Opportunities
## Content Plan
## Link Building Plan
## Priority Roadmap
## Next Actions
```

## قواعد کیفیت

- **هیچ توصیه‌ای بدون دلیل.**
- **تاثیر تجاری را بسنج** — رتبه‌ای که به درآمد وصل نیست، معیار موفقیت نیست.
- **اول بیشترین Impact.**
- **تغییر خطرناک پیشنهاد نده**؛ قبل از حذف/تغییر URL هشدار بده و نقشه‌ی 301 بخواه.
- **داده‌ی ساختگی ممنوع** — «اندازه‌گیری نشده» پاسخ محترمانه‌تری از عدد جعلی است.
- **عملیاتی بنویس** — هر آیتم باید بگوید چه کسی، روی کدام صفحه، چه کاری می‌کند.

## Next Actions

حداکثر ۵ مورد. هرکدام: کار مشخص، مالک، مهلت، معیار موفقیت.
این بخش خلاصه‌ی گزارش نیست — لیست کاری هفته‌ی آینده است.
