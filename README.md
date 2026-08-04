# SEO-Agent

An intelligent SEO management agent that performs website audits, builds keyword databases,
analyzes competitors, and generates actionable SEO reports.

یک ناوگان ایجنت سئو برای Claude Code: یک **SEO Manager** که پروژه را می‌گرداند،
هجده **ساب‌ایجنت تخصصی**، و یک **بانک کیورد** که قوانینش با کد اجرا می‌شود، نه با توصیه.

## چه چیزی داخل مخزن است

```
.claude/agents/      ۱۹ ایجنت — مدیر + متخصص‌ها
.claude/skills/      دانش مشترک: روش audit، اسکیمای دیتابیس، قالب گزارش‌ها
scripts/seodb.py     CLI بانک کیورد (فقط stdlib پایتون)
projects/            هر پروژه یک بانک کیورد مستقل
tests/               تست‌های قوانین دیتابیس + بنچمارک تشخیص شباهت
pyproject.toml       نصب seodb به‌عنوان دستور خط فرمان
CLAUDE.md            نقش پیش‌فرض و قوانین غیرقابل‌مذاکره
```

## این ابزار چه کاری **نمی‌کند**

قبل از شروع، این را بدان تا انتظارت درست باشد:

- **به هیچ ابزار سئویی وصل نمی‌شود.** نه Google Search Console، نه GA4، نه Ahrefs،
  نه SEMrush، نه PageSpeed Insights، نه هیچ API دیگری. `seodb` یک انبار داده‌ی CSV است،
  نه یک crawler و نه یک rank tracker.
- **حجم جستجو، KD، CPC، رتبه و ترافیک را خودش پیدا نمی‌کند.** این اعداد را تو وارد می‌کنی —
  دستی یا از روی export همان ابزارها (`kw add --volume ... --difficulty ...`،
  `kw check --position ... --source gsc`).
- **ستون خالی یعنی «هنوز داده‌اش را نداریم»، نه اینکه ابزار خراب است.** طبق قانون
  «داده‌ی ساختگی ممنوع» در `CLAUDE.md`، ایجنت‌ها حق ندارند این ستون‌ها را با عدد حدسی پر کنند؛
  به‌جایش در گزارش می‌نویسند `source: needed`.
- **`seodb` هیچ تغییری روی سایت نمی‌دهد** — یک انبار داده‌ی CSV است، نه یک deploy tool.

خود ایجنت‌ها (نه `seodb`) وقتی در Claude Code اجرا می‌شوند به `WebFetch`/`WebSearch` دسترسی
دارند و می‌توانند صفحه‌ای را بخوانند یا SERP را ببینند؛ اما اگر در محیطی بدون شبکه اجرا شوند،
موظف‌اند صریحاً بگویند چه چیزی را نتوانسته‌اند بررسی کنند.

**درباره‌ی تغییر کد:** ایجنت‌های `frontend-developer`، `backend-developer` و
`wordpress-master` **می‌توانند** فایل‌های پروژه‌ات را تغییر دهند. آن‌ها فقط بعد از اینکه
ایجنت تحلیل مشکل را مشخص کرد و تو تایید کردی وارد می‌شوند، و موظف‌اند قبل از هر تغییری که
روی URLها اثر دارد هشدار بدهند و نقشه‌ی 301 بنویسند. اگر نمی‌خواهی چیزی تغییر کند، صریح
بگو «فقط تحلیل کن».

## ایجنت‌ها

| ایجنت | مسئولیت |
| --- | --- |
| **`seo-manager`** | مالک پروژه، Workflow شش‌مرحله‌ای، اولویت‌بندی، گزارش نهایی |
| `seo-specialist` | crawl، index، redirect، schema، JS rendering، title، meta، heading + SEO Health Score |
| `search-specialist` | کشف کیورد، search intent، clustering، topic map، بررسی SERP |
| `competitive-analyst` | کیوردهای مشترک/مفقود، content gap، الگوی رقبا |
| `performance-engineer` | Core Web Vitals: LCP، CLS، INP، TTFB |
| `accessibility-tester` | HTML معنایی، heading، alt، ناوبری کیبورد، WCAG |
| `data-analyst` | تحلیل export سرچ کنسول و GA4 و ثبتشان در بانک |
| `content-strategist` | تقویم محتوا، brief نویسنده، ساختار مقاله، FAQ schema |
| `content-quality-editor` | کیفیت محتوا، EEAT، عمق در برابر صفحات رتبه‌دار |
| `frontend-developer` | اصلاح HTML، meta، canonical، JSON-LD، رندر کلاینت |
| `backend-developer` | اصلاح SSR، کد وضعیت، redirect، sitemap، TTFB |
| `wordpress-master` | Yoast/RankMath، permalink، آرشیو، ووکامرس |
| `link-building-analyst` | کیفیت بک‌لینک، ریسک‌ها، فرصت‌های لینک، outreach |
| `keyword-db-manager` | نگهبان بانک کیورد و تاریخچه‌ی رتبه |
| `technical-writer` | گزارش عملکرد، مانیتورینگ هفتگی، Roadmap |
| `knowledge-synthesizer` | ادغام یافته‌های چند ایجنت و حل تناقض |
| `workflow-orchestrator` · `task-distributor` · `prompt-engineer` | متا: طراحی مسیر، تقسیم کار حجیم، بهبود خود ایجنت‌ها |

Claude بر اساس درخواست، ایجنت مناسب را انتخاب می‌کند. می‌توانی صریح هم بگویی:
«با `seo-specialist` سایت را بررسی کن».

**تحلیل و اصلاح جدا هستند:** ایجنت‌های تحلیل مشکل را پیدا می‌کنند و ایجنت‌های توسعه فقط
بعد از تایید تو آن را اصلاح می‌کنند — هیچ تغییری بر اساس حدس روی کد اعمال نمی‌شود.

ایجنت‌های عمومی (توسعه، performance، accessibility، گزارش و متا) از
[VoltAgent/awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents)
(مجوز MIT) گرفته و با قوانین این مخزن تطبیق داده شده‌اند: وابستگی به `context-manager` حذف
شده، ارجاع به بانک کیورد و قانون «داده‌ی ساختگی ممنوع» اضافه شده، چک‌لیست‌های عمومی هرس
شده، و دانش تخصصی هر ایجنت زیر خط `## مرجع تخصصی` نگه داشته شده است.

## نصب

اختیاری است. با نصب، دستور `seodb` از هر مسیری در دسترس است:

```bash
pip install -e .

seodb --project projects/mysite audit
```

بدون نصب هم همه‌چیز کار می‌کند — هر `seodb` در ادامه‌ی این فایل معادل
`python3 scripts/seodb.py` است:

```bash
python3 scripts/seodb.py --project projects/mysite audit
```

نصب هیچ وابستگی‌ای نمی‌آورد؛ فقط یک console script روی همان فایل می‌سازد.

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

### ایمنی فایل‌ها

`seo-manager` ساب‌ایجنت‌های مستقل را **موازی** اجرا می‌کند، پس نوشتن هم‌زمان روی یک
بانک کیورد یک حالت عادی است، نه یک اتفاق نادر:

- هر نوشتن **اتمیک** است: ابتدا روی فایل موقتِ کنار مقصد نوشته می‌شود و بعد با
  `os.replace` جابه‌جا می‌شود. خواننده یا نسخه‌ی کامل قبلی را می‌بیند یا نسخه‌ی کامل جدید —
  هرگز فایل نیمه‌نوشته.
- هر چرخه‌ی read-modify-write زیر یک **قفل بین‌فرآیندی** (`flock`) روی همان جدول انجام
  می‌شود، پس دو `kw add` هم‌زمان هر دو ردیفشان را نگه می‌دارند. قفل به‌ازای هر جدول است،
  بنابراین نوشتن روی `keywords.csv` جلوی نوشتن روی `pages.csv` را نمی‌گیرد.
- مقداری که با `=`، `+`، `-` یا `@` شروع شود (مثلاً یک note مشکوک) موقع نوشتن با `'`
  خنثی می‌شود تا در Excel/Google Sheets به‌عنوان فرمول اجرا نشود؛ موقع خواندن دوباره
  همان مقدار اصلی برگردانده می‌شود (CSV injection — راهنمای OWASP).

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

# بنچمارک تشخیص شباهت روی بانک کیورد مصنوعی فارسی (بخشی از تست‌ها نیست)
python3 tests/bench_similarity.py --count 500 1000 2000 5000
```

بنچمارک، پیاده‌سازی قبلی (مقایسه‌ی زوجیِ همه با همه) را کنار پیاده‌سازی فعلی
(ایندکس blocking) اجرا می‌کند و **قبل از گزارش زمان، برابر بودن نتیجه‌ی هر دو را
بررسی می‌کند** — سریع‌تر شدن نباید به قیمت از دست دادن یک تطابق واقعی تمام شود.

تست‌ها روی GitHub Actions (`.github/workflows/test.yml`) با پایتون ۳.۹، ۳.۱۱ و ۳.۱۳ اجرا می‌شوند.

بدون وابستگی خارجی — فقط کتابخانه‌ی استاندارد پایتون ۳.

## قواعد کیفیت

- هیچ توصیه‌ای بدون دلیل و بدون بررسی تاثیر تجاری.
- داده‌ی ساختگی ممنوع؛ ستون خالی از عدد جعلی بهتر است.
- قبل از حذف یا تغییر URL، هشدار صریح و نقشه‌ی 301.
- خروجی همیشه اولویت‌بندی‌شده و عملیاتی.
