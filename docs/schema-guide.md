# راهنمای اسکیما (Structured Data)

مرجع تصمیم‌گیری برای JSON-LD در این مخزن. `frontend-developer` در قدم ۴ حلقه‌ی مقاله
(`docs/workflow.md`) از این استفاده می‌کند و `seo-specialist` در audit با همین معیارها
اسکیمای موجود را می‌سنجد.

## قانون صفر: اسکیما رتبه نمی‌آورد، نمایش می‌آورد

اسکیما یک فاکتور رتبه‌بندی مستقیم **نیست**. کاری که می‌کند این است که صفحه را واجد شرایط
نمایش غنی (rich result) می‌کند: ستاره، قیمت، FAQ بازشونده، breadcrumb، زمان مطالعه.
اثرش روی **CTR** است، نه روی position.

یعنی: اسکیما را روی صفحه‌ای بگذار که یا رتبه دارد یا نزدیک است. اسکیما روی صفحه‌ی
رتبه‌۸۰ هیچ کاری نمی‌کند.

## قانون یک: اسکیمای دروغ، جریمه دارد

اسکیما باید **دقیقاً همان چیزی را بگوید که کاربر روی صفحه می‌بیند**. این‌ها نقض
دستورالعمل گوگل‌اند و می‌توانند به manual action ختم شوند:

- `AggregateRating` روی صفحه‌ای که نظری ندارد، یا نظرات را نشان نمی‌دهد.
- `Product` با `price` متفاوت از قیمت واقعی صفحه.
- `FAQPage` با پرسش‌هایی که در متن صفحه وجود ندارند.
- `Review` که خودِ کسب‌وکار درباره‌ی خودش نوشته.
- markup روی محتوایی که پشت لاگین یا تب بسته پنهان است.

طبق قانون «داده‌ی ساختگی ممنوع» این مخزن: **فیلدی را که داده‌اش را نداری، ننویس.**
اسکیمای ناقصِ درست، بهتر از اسکیمای کاملِ ساختگی است.

## کدام نوع برای کدام صفحه

| نوع صفحه | اسکیمای اصلی | اضافه‌های مفید |
| --- | --- | --- |
| مقاله‌ی وبلاگ | `Article` (یا `BlogPosting`) | `BreadcrumbList`، `FAQPage` |
| راهنمای گام‌به‌گام | `HowTo` | `BreadcrumbList`، `VideoObject` |
| صفحه‌ی محصول | `Product` + `Offer` | `BreadcrumbList`، `AggregateRating` (اگر واقعی است) |
| دسته‌بندی / لیست محصول | `BreadcrumbList` + `ItemList` | — |
| صفحه‌ی پرسش‌های متداول | `FAQPage` | `BreadcrumbList` |
| صفحه‌ی خدمات | `Service` | `LocalBusiness`، `BreadcrumbList` |
| کسب‌وکار محلی | `LocalBusiness` (زیرنوع دقیق‌تر بهتر) | `openingHours`، `geo`، `sameAs` |
| صفحه‌ی اصلی | `Organization` یا `WebSite` | `SearchAction` برای sitelinks searchbox |
| رویداد | `Event` | `Offer`، `Place` |
| دستور غذا | `Recipe` | `AggregateRating`، `VideoObject` |

**`BreadcrumbList` تقریباً همیشه ارزش دارد** — ارزان است و مسیر را در نتیجه‌ی جستجو
جایگزین URL خام می‌کند.

## حداقل فیلدهای لازم

فقط فیلدهایی که گوگل برای واجد شرایط شدن لازم دارد. بقیه اختیاری‌اند و اگر داده‌شان را
نداری، نباید نوشته شوند.

### Article

```json
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "<حداکثر ۱۱۰ کاراکتر>",
  "image": ["https://example.com/img.jpg"],
  "datePublished": "2026-08-04T09:00:00+03:30",
  "dateModified": "2026-08-04T09:00:00+03:30",
  "author": {
    "@type": "Person",
    "name": "<نام واقعی نویسنده>",
    "url": "https://example.com/author/<slug>"
  },
  "publisher": {
    "@type": "Organization",
    "name": "<نام سایت>",
    "logo": { "@type": "ImageObject", "url": "https://example.com/logo.png" }
  }
}
```

`author` با نام واقعی و صفحه‌ی نویسنده، یکی از سیگنال‌های EEAT است — `Person` بنویس نه
`Organization`، مگر واقعاً تیمی نوشته شده باشد.

### FAQPage

```json
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [{
    "@type": "Question",
    "name": "<پرسش، دقیقاً همان‌طور که در صفحه آمده>",
    "acceptedAnswer": { "@type": "Answer", "text": "<پاسخ کامل، همان متن صفحه>" }
  }]
}
```

هر پرسش و پاسخ **باید** در متن قابل‌مشاهده‌ی صفحه هم باشد. پرسش‌ها را از
People Also Ask و question keywordهای بانک بردار.

### Product

```json
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "<نام محصول>",
  "image": ["https://example.com/product.jpg"],
  "description": "<توضیح>",
  "sku": "<کد>",
  "brand": { "@type": "Brand", "name": "<برند>" },
  "offers": {
    "@type": "Offer",
    "url": "https://example.com/product",
    "priceCurrency": "IRR",
    "price": "12500000",
    "availability": "https://schema.org/InStock"
  }
}
```

`price` باید با قیمت نمایش‌داده‌شده یکی باشد. `availability` را با موجودی واقعی هماهنگ نگه
دار — اسکیمای «موجود» روی محصول ناموجود، تجربه‌ی بد و ریسک جریمه است.

### HowTo

```json
{
  "@context": "https://schema.org",
  "@type": "HowTo",
  "name": "<عنوان راهنما>",
  "step": [
    { "@type": "HowToStep", "name": "<گام ۱>", "text": "<توضیح گام>" }
  ]
}
```

### BreadcrumbList

```json
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    { "@type": "ListItem", "position": 1, "name": "خانه", "item": "https://example.com/" },
    { "@type": "ListItem", "position": 2, "name": "<دسته>", "item": "https://example.com/<cat>/" },
    { "@type": "ListItem", "position": 3, "name": "<صفحه‌ی فعلی>" }
  ]
}
```

آخرین آیتم `item` نمی‌گیرد — خودِ صفحه‌ی فعلی است.

## قواعد پیاده‌سازی

- **JSON-LD در `<head>`**، نه Microdata و نه RDFa. گوگل JSON-LD را توصیه می‌کند و
  نگهداری‌اش هم ساده‌تر است چون از HTML جداست.
- **چند اسکیما در یک صفحه** مجاز است. یا چند بلاک `<script type="application/ld+json">`
  جدا بگذار، یا یک آرایه در `@graph`.
- **یک `Article` به‌ازای هر صفحه**، نه چند تا. دو `Article` روی یک URL یعنی ابهام.
- **URLها مطلق باشند**، نه نسبی.
- **`dateModified` را واقعاً به‌روز کن** وقتی محتوا عوض می‌شود؛ تغییر دادنش بدون تغییر
  محتوا، دستکاری است.
- در وردپرس معمولاً Yoast/RankMath خودشان `Article` و `BreadcrumbList` را تولید می‌کنند.
  **قبل از افزودن دستی، خروجی فعلی را ببین** — اسکیمای تکراری بدتر از نبودش است.
  (`wordpress-master` مسئول این بررسی است.)

## اعتبارسنجی — قبل از اینکه بگویی تمام شد

```bash
# اسکیمای فعلی صفحه را ببین
curl -s <url> | grep -A 40 'application/ld+json'
```

بعد با این دو ابزار تایید کن و **نتیجه را در گزارش بنویس**:

| ابزار | چه می‌گوید |
| --- | --- |
| Rich Results Test (گوگل) | آیا صفحه واجد شرایط نمایش غنی است |
| Schema Markup Validator (schema.org) | آیا markup از نظر ساختاری معتبر است |

بخش «Enhancements» سرچ کنسول هم خطاهای اسکیمای کل سایت را نشان می‌دهد — این تنها جایی
است که می‌فهمی گوگل واقعاً چه برداشتی کرده. این مخزن به سرچ کنسول وصل نیست؛ export را
از کاربر بگیر (`data-analyst`).

## اشتباهات رایج

| اشتباه | چرا بد است |
| --- | --- |
| `AggregateRating` بدون نظر واقعی | نقض دستورالعمل، ریسک manual action |
| `FAQPage` با پرسش‌هایی که در صفحه نیستند | همان — و FAQ در نتایج حذف می‌شود |
| اسکیما روی محتوای پنهان (تب بسته، پشت لاگین) | گوگل آن را نامعتبر می‌داند |
| کپی اسکیمای صفحه‌ی دیگر بدون تغییر داده | داده‌ی اشتباه در تمام صفحات |
| اسکیما به‌جای رفع مشکل ایندکس | صفحه‌ای که ایندکس نیست، rich result نمی‌گیرد |
| `headline` بلندتر از ۱۱۰ کاراکتر | گوگل نادیده می‌گیرد |
| انتظار افزایش رتبه از اسکیما | اثرش روی CTR است نه position — انتظار غلط، ارزیابی غلط |
