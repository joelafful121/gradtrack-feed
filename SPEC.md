# GradTrack research spec (read fully before starting)

Goal: find UK graduate schemes / graduate jobs that START AFTER summer 2027 graduation (roughly July–December 2027), are OPEN NOW or CONFIRMED OPENING SOON, and record their entry requirements in a structured way so a tracker can filter by a student's degree subject, A-levels, GCSEs and degree class. Today is 11 October 2026.

## Include only if ALL true
- Graduate scheme or graduate-level job for 2027 graduates (NOT internships, placements, spring weeks, insight days, apprenticeships, experienced hires).
- Based in the UK (record the cities where you can be based).
- Start date is in 2027 after graduation (July–Dec 2027). If the posting says just "2027" or "September 2027", fine. Exclude 2026 or Jan–Jun 2027 starts.
- Exception – law: solicitor training contracts open now for a 2028 or 2029 start are allowed (law firms recruit two years ahead). Record the real start in "start" and say so in "notes".
- Location: the tracker only shows roles based in London, Birmingham, Manchester, Leeds or Liverpool (or ["UK-wide"]). Only add roles that can be based in at least one of those five cities; list every city the posting names.
- Application is open now (deadline in the future or rolling) OR the employer has a confirmed 2027 posting that opens soon (status "soon"; only if there is a real vacancy page or an official programme page saying it opens in the coming weeks).
- You have checked the actual posting (WebFetch it). The url must be the SPECIFIC vacancy/posting page (with the job title/ID), never a careers homepage. If only a programme page exists for a "soon" role, use it and set status "soon".

## How to research
- Use WebSearch and WebFetch. Good sources: employer careers sites, TargetJobs, Bright Network, Prospects, Gradcracker, Milkround, graduate-jobs.com, Higherin, Indeed UK.
- Apify tools (mcp__Apify__apify--web-fetch / rag-web-browser) cost the user real money: use AT MOST 4 Apify calls in total, only for pages WebFetch cannot open.
- Never guess requirements. If the posting doesn't state a requirement, use null and say "Not stated" in reqText.
- Aggregator pages often show stale data; prefer the employer's own page for deadlines and requirements. If an aggregator is the only source, say so in src.

## Output
Write a JSON array to the file path given in your task (pretty-printed, UTF-8). Each object:
{
 "id": "kebab-case-unique, employer-programme-city e.g. kpmg-audit-manchester",
 "emp": "Employer name",
 "title": "Programme / job title as posted",
 "url": "https://... specific posting",
 "src": "Where you found it (e.g. 'KPMG careers site', 'TargetJobs')",
 "disciplines": ["any"]  OR a subset of the DISCIPLINE KEYS below (degree subjects the employer accepts),
 "area": one of the AREA labels below,
 "cities": ["London","Manchester"] (UK cities you can be based in; use ["UK-wide"] if the posting says you can be placed anywhere / national rotations),
 "start": "Sep 2027" (as stated),
 "dl": "YYYY-MM-DD" or null,
 "dlNote": "e.g. 'rolling – may close early'" or "",
 "status": "open" or "soon",
 "salary": "£xx,xxx" or "Not stated",
 "degreeMin": "2:1" | "2:2" | "Third" | null,
 "ucasMin": number or null (minimum UCAS tariff points; if a contextual lower offer exists put the standard figure here and mention the contextual one in reqText),
 "alevels": "BBB" or null (minimum grades in your top three A-levels as letters, highest first, e.g. 'three A-levels at A*-C' -> "CCC", 'ABB' -> "ABB"),
 "alevelSubject": {"subject":"Maths","grade":"B"} or null (only if a specific A-level subject+grade is required),
 "gcseMaths": number or null (minimum GCSE Maths grade on the 9–1 scale; convert old letter grades as A* = 8, A = 7, B = 5, C = 4),
 "gcseEnglish": number or null (same scale),
 "licence": true or false (true only if a full driving licence is required),
 "reqText": "One short line with the entry requirements as stated, e.g. '2:1 any subject; 120 UCAS; GCSE Maths & English grade 5'",
 "qual": "Professional qualification funded (e.g. 'ACA', 'CIMA', 'Chartered Engineer pathway') or 'None'",
 "notes": "One short factual note that matters to an applicant (relocation, travel, one-application rule, security clearance, nationality). Can be ''.",
 "checked": "2026-10-11"
}

DISCIPLINE KEYS (degree subjects):
"accounting-finance", "business", "economics", "law", "computing", "engineering", "maths-physics", "sciences", "social-sciences", "humanities", "creative", "built-environment"
(Use ["any"] when the scheme accepts any degree subject. If it lists specific subjects, map them to these keys, e.g. 'numerate degree' -> ["accounting-finance","economics","maths-physics","engineering","computing","sciences"]; 'STEM' -> ["computing","engineering","maths-physics","sciences"].)

AREA labels:
"Audit & accounting", "Tax", "Banking & markets", "Asset & wealth management", "Insurance & risk", "Corporate finance", "Consulting", "Law", "Public sector", "Engineering", "Technology", "Data & analytics", "Science & healthcare", "Marketing & media", "Retail & commercial", "HR & people", "Property & construction", "Operations & supply chain", "Teaching & social impact"

Quality over quantity: every entry must be verified. Aim for the target number in your task but never pad with unverified roles. If a firm has the same programme in several cities, ONE entry with all the cities is fine.

When done, reply with: the file path, how many roles, and a list of anything you couldn't verify or that looked closed.
