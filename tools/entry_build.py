#!/usr/bin/env python3
"""Build entry.json (graduate & entry-level job ads) from raw Indeed results.

Usage:
  python3 tools/entry_build.py RAW1.json [RAW2.json ...]   # merges into entry.json in the repo root

RAW files are the JSON saved from Apify `get-dataset-items` on a valig/indeed-jobs-scraper run
(shape {"items":[...]} or a plain list). Fields used: key, title, jobUrl, url, datePublished,
expirationDate, employer.name, location.city, baseSalary, description.text, attributes, occupations, jobTypes.

Rules (see SPEC.md "Job ads"): only the five cities (and their metro towns); graduate / junior / trainee /
entry-level professional roles; no trades, care, retail-floor or hospitality jobs; nothing asking for 2+ years'
experience; ads older than MAX_AGE days are dropped; curated schemes in jobs.json win over job ads.
"""
import datetime as dt
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = dt.date.today()
MAX_AGE_JOB = 60      # days since posted
MAX_AGE_SCHEME = 150  # graduate programmes stay up longer
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                         "september", "october", "november", "december"], 1)}

# ---------- location ----------
METRO = {
    "London": """london|city of london|greater london|westminster|croydon|wembley|stratford|canary wharf|hammersmith|kingston upon thames|
      richmond|bromley|harrow|ilford|romford|enfield|barnet|sutton|hounslow|ealing|uxbridge|twickenham|wimbledon|greenwich|woolwich|
      lewisham|camden|islington|southwark|lambeth|hackney|tower hamlets|brent|chiswick|battersea|fulham|chelsea|kensington|shoreditch|
      holborn|paddington|hayes|feltham|heathrow|edgware|walthamstow|leyton|tottenham|wood green|brixton|clapham|putney|wandsworth|
      mitcham|morden|sidcup|bexleyheath|orpington|beckenham|erith|barking|dagenham|stanmore|pinner|ruislip|northolt|greenford|southall|
      acton|hendon|finchley|kilburn|southgate|eltham|catford|deptford|bermondsey|whitechapel|poplar|east ham|canning town|surbiton|
      new malden|carshalton|wallington|purley|coulsdon|thornton heath|streatham|tooting|balham|vauxhall|kew|teddington|isleworth|
      brentford|hillingdon|west drayton|park royal|white city|kings cross|king's cross|marylebone|mayfair|soho|covent garden|
      farringdon|clerkenwell|aldgate|bank|moorgate|liverpool street|london bridge|waterloo|victoria|euston|old street|docklands|
      north greenwich|bow|mile end|hornchurch|upminster|chingford|edmonton|harlesden|neasden|colindale|mill hill|wembley park|
      south kensington|notting hill|shepherd's bush|shepherds bush|archway|highbury|holloway|dalston|bethnal green|limehouse|wapping|
      rotherhithe|peckham|camberwell|dulwich|sydenham|forest hill|crystal palace|norwood|kennington|elephant and castle|belgravia|pimlico|
      knightsbridge|st john's wood|swiss cottage|hampstead|highgate|muswell hill|crouch end|stoke newington|bloomsbury|fitzrovia""",
    "Birmingham": """birmingham|solihull|sutton coldfield|west bromwich|smethwick|oldbury|halesowen|edgbaston|erdington|selly oak|bournville|
      longbridge|castle bromwich|shirley|digbeth|aston|bordesley|small heath|kings heath|harborne|moseley|acocks green|yardley|
      hall green|northfield|tipton|wednesbury|perry barr|nechells|saltley|marston green|chelmsley wood""",
    "Manchester": """manchester|salford|trafford|old trafford|trafford park|stockport|cheadle|sale|altrincham|stretford|bolton|bury|oldham|
      rochdale|wigan|ashton-under-lyne|ashton under lyne|stalybridge|hyde|denton|didsbury|wythenshawe|manchester airport|eccles|
      swinton|middleton|prestwich|heywood|leigh|atherton|hazel grove|bramhall|mediacityuk|media city|salford quays|urmston|
      chorlton|levenshulme|ancoats|hulme|fallowfield|withington|cheadle hulme|marple|droylsden|failsworth|radcliffe|whitefield|
      ramsbottom|horwich|westhoughton|farnworth|walkden|irlam|partington|timperley|hale|dukinfield|mossley""",
    "Leeds": """leeds|horsforth|pudsey|morley|garforth|wetherby|otley|guiseley|yeadon|rothwell|seacroft|headingley|holbeck|thorpe park|
      kirkstall|rawdon|leeds bradford airport|beeston|armley|bramley|chapel allerton|roundhay|crossgates|cross gates|halton|
      kippax|boston spa|methley|drighlington|gildersome|calverley|farsley|stanningley|moortown|alwoodley|adel|cookridge|meanwood|
      hunslet|burley|kirkstall forge|whitehall""",
    "Liverpool": """liverpool|bootle|knowsley|huyton|kirkby|prescot|halewood|speke|st helens|st. helens|birkenhead|wallasey|wirral|
      bebington|crosby|maghull|formby|southport|heswall|hoylake|west kirby|litherland|netherton|aintree|garston|allerton|
      wavertree|toxteth|everton|anfield|walton|childwall|woolton|old swan|kensington liverpool|newton-le-willows|haydock|rainhill|
      eccleston|whiston|ellesmere port""",
}
METRO_RE = {c: re.compile(r"^(?:%s)$" % "|".join(x.strip() for x in v.replace("\n", "").split("|") if x.strip()), re.I)
            for c, v in METRO.items()}
CITY_ORDER = ["London", "Birmingham", "Manchester", "Leeds", "Liverpool"]


REGION = {"greater london": "London", "city of london": "London", "greater manchester": "Manchester", "merseyside": "Liverpool",
          "west midlands": "Birmingham", "west yorkshire": "Leeds", "city and borough of leeds": "Leeds", "city of leeds": "Leeds",
          "city of birmingham": "Birmingham", "city of manchester": "Manchester", "city of liverpool": "Liverpool"}


def map_city(raw):
    if not raw:
        return None
    t = raw.strip().lower().replace(", uk", "")
    t = re.sub(r"\s*\(.*?\)\s*", " ", t).strip()
    t = re.sub(r"\s+area$", "", t)
    if t in REGION:
        return REGION[t]
    for c in CITY_ORDER:
        if METRO_RE[c].match(t):
            return c
    return None


# ---------- what counts as a graduate / entry-level role ----------
DENY_TITLE = re.compile(r"""\b(care assistant|carer|care worker|support worker|healthcare assistant|health care assistant|nursing assistant|
  driver|hgv|lgv|van\b|delivery driver|delivery rider|delivery associate|delivery assistant|courier|warehouse operative|warehouse assistant|
  warehouse worker|warehouse associate|picker|packer|operative|labourer|cleaner|
  cleaning|housekeep|chef|cook\b|kitchen|porter|waiter|waitress|bartender|bar staff|barista|front of house|crew member|
  team member|cashier|checkout|retail assistant|sales assistant|store assistant|shop assistant|customer assistant|bar\b|
  merchandiser \(field|security officer|door supervisor|steward|nanny|childminder|nursery|early years|groom|gardener|landscaper|
  plumber|electrician|gas engineer|heating engineer|mechanic|vehicle technician|tyre|valeter|bodyshop|panel beater|joiner|carpenter|
  bricklayer|plasterer|painter|decorator|roofer|scaffold|welder|fabricator|machinist|cnc|forklift|fork lift|loader|sorter|
  multi[- ]?skilled|maintenance operative|handyman|caretaker|dental nurse|pharmacy assistant|optical assistant|phlebotomist|
  hairdress|beauty|nail tech|barber|massage|fitness instructor|personal trainer|lifeguard|swim|cabin crew|flight attendant|
  receptionist|call centre|contact centre|telesales|door to door|field sales|market research interviewer|mystery shopper|insight day|insight week|insight programme|
  bus driver|train driver|tram|taxi|chauffeur|postman|postwoman|traffic marshal|parking|cleaner|domestic|laundry|
  apprentice|apprenticeship|internship|intern\b|placement|work experience|spring week|summer internship|summer placement|summer job|volunteer|
  phd|studentship|postdoc|post-doc|fellowship|lecturer|professor|consultant psychiatrist|registrar|locum|nurse\b|midwife|
  doctor|gp\b|dentist|optometrist|physiotherapist|radiographer|paramedic|social worker \(qualified|senior|sr\.?\s|lead\b|
  principal|head of|director|chief|vp\b|vice president|partner\b|managing|supervisor|team leader|shift leader|foreman|
  part[- ]time|weekend|evening|night|temporary|temp\b|ad hoc|zero hours|bank staff|seasonal|christmas|self[- ]employed|
  commission only|franchise|tutor \(online|online tutor|ambassador|promoter|brand rep|ii\b|iii\b|level 3|level 4|fellow\b|clinical fellow|
  croupier|dealer|bookmaker|betting|cover supervisor|exam invigilator|invigilator|lifeguard|freelance|branch management trainee|
  restaurant|hospitality|hotel|catering|food and beverage|f&b|retail management trainee|store manager|duty manager|
  live host|streamer|sales associate|research associate|research fellow|postdoctoral|multifunctional|visual merchandiser|
  stylist|model\b|actor|dancer|singer|musician|photographer|videographer \(freelance|tiktok live|experienced|assistant or associate|
  associate or assistant)""".replace("\n", "").replace("  ", ""), re.I)
TRADE_ENG = re.compile(r"(water|hygiene|escalator|\blift\b|earthing|\bgas\b|heating|boiler|field service|service engineer|field engineer|maintenance|"
                       r"installation|installer|repair|hvac|fire|alarm|security systems|cctv|telecom|cable|fibre|solar|ev charg|plumb|"
                       r"refrigeration|air con|pest|drainage|lightning|asbestos|legionella|calibration|monitoring technician|vehicle|"
                       r"motor|automotive|tyre|glazing|window|roofing|damp|locksmith|electrical installer|approved electrician|"
                       r"scaffold|crane|plant operator|surveying technician)", re.I)
EXP_REQUIRED = re.compile(r"(?<!no )(?<!without )(?:proven|previous|prior|demonstrable|significant|extensive|substantial|solid|strong) "
                          r"(?:\w+ ){0,3}experience(?! (?:is )?(?:desirable|preferred|an advantage|a plus|beneficial|not essential|not required))", re.I)
MANAGER = re.compile(r"\bmanager\b", re.I)
ENTRY_WORD = re.compile(r"\b(graduate|grad\b|junior|jnr|trainee|entry[- ]level|assistant|associate|apprentice|new grad|early careers|"
                        r"school leaver|starter|first role|no experience)\b", re.I)
PROF_WORD = re.compile(r"""\b(accountant|accounts|accounting|audit|tax|finance|financial|payroll|ledger|credit control|analyst|analytics|
  data|developer|software|engineer|engineering|programmer|devops|cloud|cyber|security analyst|it support|service desk|helpdesk|
  technical support|web|digital|product|ux|ui|designer|design|consultant|consulting|advisory|adviser|advisor|paraplanner|
  solicitor|paralegal|legal|lawyer|conveyanc|litigation|compliance|risk|underwrit|claims|actuar|insurance|broker|investment|
  fund|wealth|banking|bank|trader|trading|markets|kyc|aml|fraud|surveyor|quantity|planner|planning|architect|architectural|
  site manager|site engineer|construction|property|estate|lettings|building|facilities|scientist|science|laboratory|lab\b|
  chemist|biolog|research|researcher|clinical|pharma|regulatory|quality|qc|qa|environmental|ecolog|sustainability|psycholog|
  wellbeing practitioner|behavioural|marketing|social media|content|communications|comms|pr\b|public relations|media|
  journalist|editor|editorial|copywriter|seo|ppc|brand|advertising|creative|producer|production|events|recruitment|recruiter|
  resourcer|talent|hr\b|human resources|people|learning|l&d|training coordinator|sales|business development|account executive|
  account manager|customer success|buyer|buying|merchandis|category|commercial|e-?commerce|operations|supply chain|logistics|
  procurement|purchasing|inventory|demand|project|programme|coordinator|co-ordinator|administrator|officer|executive|policy|
  government|civil service|council|public sector|caseworker|teacher|teaching|education|school|fundraising|charity|youth|
  community|housing|management trainee|graduate|patent|negotiator|surveying)""".replace("\n", "").replace("  ", ""), re.I)
EXP_RE = re.compile(r"(\d+)\s*\+?\s*(?:-|to|–)?\s*\d*\s*\+?\s*years?['’]?\s*(?:of\s+)?(?:[a-z\-/&]+\s+){0,4}experience", re.I)
PQE_RE = re.compile(r"\b\d+\s*(?:-|to|–)?\s*\d*\s*years?\s*pqe\b|\bpqe\b", re.I)


def min_years(text):
    best = None
    for m in EXP_RE.finditer(text or ""):
        n = int(m.group(1))
        ctx = text[max(0, m.start() - 40):m.start()].lower()
        if any(w in ctx for w in ("after ", "within ", "over the ", "in your first", "next ", "for ", "programme of", "over ")):
            continue
        if n <= 15:
            best = n if best is None else min(best, n)
    return best


# ---------- sector ----------
AREA_RULES = [
    ("Psychology & behavioural science", r"psycholog|wellbeing practitioner|\bpwp\b|behavioural scien|behavioral scien|human factors|cbt therapist|mental health (?:assistant|practitioner|support graduate)"),
    ("Law", r"solicitor|paralegal|\blegal\b|lawyer|barrister|conveyanc|litigation|law graduate|\bcilex\b|trainee legal|legal secretary|probate"),
    ("Tax", r"\btax\b|taxation|vat\b"),
    ("Insurance & risk", r"insurance|underwrit|claims|actuar|\brisk\b|broker|reinsurance|loss adjust|compliance"),
    ("Banking & markets", r"\bbank|banking|trader|trading|markets|\bkyc\b|\baml\b|financial crime|fraud|credit analyst|lending|mortgage|payments|treasury analyst"),
    ("Asset & wealth management", r"wealth|asset management|\bfund\b|funds|investment|portfolio|paraplanner|financial advis|financial planner|pension"),
    ("Audit & accounting", r"audit|financial assistant|finance officer|accountant|accounts|accounting|bookkeep|payroll|ledger|credit control|\baca\b|\bacca\b|\bcima\b|\baat\b|purchase ledger|finance assistant|finance administrator|billing"),
    ("Corporate finance", r"corporate finance|\bm&a\b|mergers|deals|transaction services|valuations|restructuring|fp&a|financial analyst|finance analyst|commercial finance|finance graduate|finance trainee|graduate finance|finance programme|finance scheme|financial planning|\bfinance\b"),
    ("Marketing & media", r"press officer|press assistant|\bpress\b|market research|consumer research|marketing|social media|content|communications|\bcomms\b|\bpr\b|public relations|media|journalist|editor|editorial|copywriter|\bseo\b|\bppc\b|brand|advertising|creative|producer|production assistant|events|digital executive|influencer|graphic design|motion design"),
    ("HR & people", r"\bhr\b|human resources|\bpeople\b|recruitment|recruiter|resourcer|talent|learning and development|learning & development|\bl&d\b|training coordinator|payroll and hr|onboarding"),
    ("Data & analytics", r"\bdata\b|analytics|insight|\bbi\b|business intelligence|reporting analyst|\bmi analyst|statistic|data scien|machine learning|\bai\b"),
    ("Technology", r"software|developer|programmer|devops|cloud|platform engineer|front[- ]?end|back[- ]?end|full[- ]?stack|\bqa\b|tester|test engineer|site reliability|network (?:engineer|analyst|support|administrator|security)|systems (?:analyst|administrator|support|engineer)|it systems|\bit\b|service desk|helpdesk|help desk|technical support|cyber|security analyst|soc analyst|web|product manager|product owner|product analyst|\bux\b|\bui\b|(?:it|cloud|platform) infrastructure|technology|technical consultant|salesforce|\bsap\b|\berp\b|\bcrm\b|digital"),
    ("Science & healthcare", r"research|laborator|\blab\b|scientist|chemist|biolog|microbio|clinical|pharma|research associate|healthcare scien|medical|\bnhs\b|\bqc\b|regulatory affairs|veterinar|environmental|ecolog|geolog|biomedical|formulation|life science|healthcare|health"),
    ("Engineering", r"engineer|engineering|\bcad\b|technician|mechanical|electrical|civil|structural|manufacturing|aerospace|nuclear|automation|controls|process"),
    ("Property & construction", r"surveyor|surveying|quantity|site manager|construction|property|estate|lettings|planner|planning|architect|building|facilities|real estate|land|housing development|cost consultant|project manager"),
    ("Consulting", r"consultant|consulting|advisory|business analyst|strategy|transformation|change analyst"),
    ("Public sector", r"civil service|government|council|policy|public sector|local authority|parliament|caseworker|\bhmrc\b|\bdwp\b|ministry|police|fire service|department for|cabinet office|ombudsman|regulator|housing"),
    ("Teaching & social impact", r"teacher|teaching|tutor|school|education|charity|fundraising|youth|social work|community|volunteer|impact|lecturer|learning support"),
    ("Data & analytics", r"\banalyst\b"),
    ("Retail & commercial", r"sales|business development|account executive|account manager|customer success|buyer|buying|merchandis|category|commercial|retail|e-?commerce|store|area manager|client executive|lead generation"),
    ("Operations & supply chain", r"operations|supply chain|logistics|procurement|purchasing|inventory|demand|planner|transport|shipping|freight|warehouse|production planner|project|programme|coordinator|co-ordinator|administrator|officer|executive|assistant|management trainee"),
]
AREA_RULES = [(a, re.compile(p, re.I)) for a, p in AREA_RULES]
RECRUIT_CONS = re.compile(r"recruitment consultant|recruiter|resourcer", re.I)


PHYS_ENG = re.compile(r"engineer", re.I)
NOT_PHYS = re.compile(r"software|data|cloud|devops|platform|front|back[- ]?end|full[- ]?stack|test|\bqa\b|site reliability|security|cyber|"
                      r"network|systems|\bit\b|support|machine learning|\bai\b|\bml\b|sales|solutions|pre-?sales|web|application|integration|"
                      r"salesforce|product|game|graphics|prompt|analytics", re.I)
SALES_CONS = re.compile(r"sales consultant|sales executive|sales advis|sales repres|car sales|travel consultant|beauty consultant|lettings consultant", re.I)


def classify(title, occ):
    t = title or ""
    if RECRUIT_CONS.search(t):
        return "HR & people"
    if re.search(r"psycholog|wellbeing practitioner", t, re.I):
        return "Psychology & behavioural science"
    if re.search(r"patent|trade mark|trademark", t, re.I):
        return "Law"
    if PHYS_ENG.search(t) and not NOT_PHYS.search(t):
        return "Engineering"
    if SALES_CONS.search(t) or re.search(r"\bbuyer\b|buying|merchandis|allocat|channel trading|retail planner|stock planner|range planner", t, re.I):
        return "Retail & commercial"
    if re.search(r"demand plan|supply plan|production plan|planning executive|planning analyst|planning coordinator|supply chain|logistics|procurement", t, re.I):
        return "Operations & supply chain"
    for area, rx in AREA_RULES:
        if rx.search(t):
            return area
    for area, rx in AREA_RULES:
        if occ and rx.search(occ):
            return area
    return None


# ---------- requirements ----------
DISC_WORDS = [
    ("computing", r"computer science|computing|software engineering|information technology|\bit\b|informatics|cyber"),
    ("engineering", r"engineering"),
    ("maths-physics", r"mathemat|\bmaths?\b|physics|statistic|actuarial|quantitative"),
    ("sciences", r"chemistry|biology|biochem|biomedical|life science|pharmacolog|pharmacy|microbiolog|environmental science|geolog|geoscience|natural science|\bscience\b|\bstem\b"),
    ("accounting-finance", r"accounting|accountancy|\bfinance\b"),
    ("economics", r"economics|econometric"),
    ("business", r"\bbusiness\b|management|marketing"),
    ("law", r"\blaw\b|\bllb\b"),
    ("psychology", r"psycholog"),
    ("social-sciences", r"sociology|politics|geography|criminology|social science|social policy|international relations"),
    ("humanities", r"history|english|languages|philosophy|classics|humanities"),
    ("creative", r"graphic design|fashion|product design|art and design|fine art|\bart\b|film|journalism|music|animation|illustration"),
    ("built-environment", r"surveying|construction|architecture|town planning|\bplanning\b|real estate|built environment|property"),
]
DISC_WORDS = [(k, re.compile(p, re.I)) for k, p in DISC_WORDS]
STEM = ["computing", "engineering", "maths-physics", "sciences"]
NUMERATE = ["accounting-finance", "economics", "maths-physics", "engineering", "computing", "sciences"]
ANY_RE = re.compile(r"any (?:degree|discipline|subject)|all (?:degree )?disciplines|degree in any|from any (?:degree|discipline|background)|"
                    r"any academic background|all backgrounds|no degree|degree not required|don't need a degree|do not need a degree", re.I)


def disciplines(title, area, text):
    if area == "Law" and re.search(r"trainee solicitor|training contract|solicitor apprentice", title or "", re.I):
        return ["any"]
    if ANY_RE.search(text or ""):
        return ["any"]
    found = set()
    for m in re.finditer(r"degree|graduate in|qualification in|bsc|beng|meng|ba\b|msc", text or "", re.I):
        win = text[max(0, m.start() - 70):m.end() + 90]
        if re.search(r"\bstem\b", win, re.I):
            found.update(STEM)
        if re.search(r"numerate|numerical", win, re.I):
            found.update(NUMERATE)
        for k, rx in DISC_WORDS:
            if rx.search(win):
                found.add(k)
    found.discard("business") if len(found) > 3 else None
    t = (title or "").lower()
    if not found:
        if area == "Engineering" and re.search(r"engineer", t) and not re.search(r"software|sales|support|service desk|data|cloud|devops|network", t):
            found.update(["engineering", "maths-physics"])
        elif re.search(r"chemist|biolog|microbiolog|laborator|\blab\b|scientist", t):
            found.update(["sciences"])
        elif re.search(r"psycholog", t):
            found.update(["psychology"])
        elif re.search(r"architect(?!ure)|architectural", t) and area == "Property & construction":
            found.update(["built-environment", "creative"])
    if not found:
        return ["any"]
    if len(found) >= 9:
        return ["any"]
    return sorted(found)


def degree_min(text):
    hits = []
    for m in re.finditer(r"\b2[:.]1\b|upper second|\b2[:.]2\b|lower second|first[- ]class|\b1st class", text or "", re.I):
        win = text[max(0, m.start() - 60):m.end() + 60].lower()
        if not re.search(r"degree|grade|classification|honours|hons|achiev|predicted|minimum|at least", win):
            continue
        s = m.group(0).lower()
        hits.append("2:1" if s.startswith("2") and s[2] == "1" or "upper" in s else "2:2" if s.startswith("2") or "lower" in s else "First")
    if not hits:
        return None
    order = {"Third": 1, "2:2": 2, "2:1": 3, "First": 4}
    return min(hits, key=lambda h: order[h])


def ucas_min(text):
    vals = [int(m.group(1)) for m in re.finditer(r"\b(\d{2,3})\s*\+?\s*ucas", text or "", re.I) if 48 <= int(m.group(1)) <= 200]
    return min(vals) if vals else None


AL_RE = re.compile(r"\b(A\*A\*A\*|A\*A\*A|A\*AA|AAA|AAB|ABB|BBB|BBC|BCC|CCC|CCD|CDD|DDD|ABC|AAC|BBD|BCD|CCE)\b")


def alevels(text):
    out = []
    for m in re.finditer(r"a[- ]?levels?", text or "", re.I):
        win = text[max(0, m.start() - 60):m.end() + 60]
        for g in AL_RE.findall(win):
            out.append(g)
    if not out:
        return None
    pts = {"A*": 56, "A": 48, "B": 40, "C": 32, "D": 24, "E": 16}

    def score(g):
        s, i = 0, 0
        while i < len(g):
            if g[i] == "A" and i + 1 < len(g) and g[i + 1] == "*":
                s += 56; i += 2
            else:
                s += pts[g[i]]; i += 1
        return s
    return min(out, key=score)


GCSE_GRADE = re.compile(r"grade[s]?\s*([4-9])\b|\b([4-9])\s*(?:/|or)\s*[A-C]\b|\b[A-C]\*?\s*(?:/|or)\s*([4-9])\b|grade[s]?\s*([A-C])\b|\b([4-9])\s*(?:or above|\+|and above)", re.I)


def gcse(text):
    gm = ge = None
    for sent in re.split(r"(?<=[.;\n•])", text or ""):
        if "gcse" not in sent.lower():
            continue
        sent = re.sub(r"\b([1-9])\s*(?:-|–|to)\s*([1-9])\b", lambda m: str(min(int(m.group(1)), int(m.group(2)))), sent)
        sent = re.sub(r"\bA\*?\s*(?:-|–|to)\s*([A-E])\b", r"\1", sent)
        grades = []
        for m in GCSE_GRADE.finditer(sent):
            g = next(x for x in m.groups() if x)
            grades.append({"A": 7, "B": 5, "C": 4}.get(g.upper(), None) if g.isalpha() else int(g))
        grades = [g for g in grades if g]
        if not grades:
            continue
        g = min(grades)
        low = sent.lower()
        if re.search(r"math", low):
            gm = g if gm is None else min(gm, g)
        if re.search(r"english", low):
            ge = g if ge is None else min(ge, g)
    return gm, ge


LIC_RE = re.compile(r"(?:full|valid|clean|current)\s+(?:uk\s+|manual\s+|uk manual\s+)?driv(?:ing|er'?s)\s+licen[cs]e|driv(?:ing|er'?s)\s+licen[cs]e\s+(?:is\s+)?(?:essential|required|needed|necessary|a must|mandatory)|must (?:be able to )?drive|access to (?:a|your own) (?:car|vehicle)|own (?:car|transport|vehicle)", re.I)
LIC_SOFT = re.compile(r"desirable|preferred|advantage|beneficial|not essential|not required|would be (?:nice|great|useful)|ideally|bonus|helpful|but not", re.I)


def licence(text, attrs):
    for m in LIC_RE.finditer(text or ""):
        win = text[max(0, m.start() - 50):m.end() + 60]
        if not LIC_SOFT.search(win):
            return True
    if attrs and ("Driving Licence" in attrs or "Access to vehicle required" in attrs) and not re.search(r"licen[cs]e[^.]{0,40}(desirable|preferred|advantage|not essential)", text or "", re.I):
        return True
    return False


QUALS = [("ACA", r"\baca\b|icaew"), ("ACCA", r"\bacca\b"), ("CIMA", r"\bcima\b"), ("CTA", r"\bcta\b"), ("ATT", r"\batt\b"),
         ("AAT", r"\baat\b"), ("CIPD", r"\bcipd\b"), ("CIPS", r"\bcips\b"), ("CII", r"\bcii\b"), ("CFA", r"\bcfa\b"),
         ("RICS APC", r"\bapc\b|\brics\b"), ("SQE", r"\bsqe\b"), ("CILEx", r"\bcilex\b"), ("Chartered engineer", r"chartership|\bceng\b|\bieng\b"),
         ("IMC", r"\bimc\b"), ("CIM", r"\bcim\b"), ("PGCE / QTS", r"\bqts\b|\bpgce\b"), ("BPS", r"\bbps\b")]
QUALS = [(q, re.compile(p, re.I)) for q, p in QUALS]


def qual(text):
    q = [n for n, rx in QUALS if rx.search(text or "")][:2]
    if not q:
        return "None"
    funded = re.search(r"fully funded|study support|sponsor|we(?:'ll| will) pay for|paid for|funded (?:study|qualification|training)", text or "", re.I)
    return " / ".join(q) + (" (funded)" if funded else "")


def deadline(text, exp_ms):
    if exp_ms:
        try:
            d = dt.datetime.fromtimestamp(exp_ms / 1000, dt.timezone.utc).date()
            if d >= TODAY:
                return d.isoformat()
        except Exception:
            pass
    rx = re.compile(r"(?:closing date|deadline|applications? close|closes|close on|open until|apply by|until|no later than)[^.\n]{0,40}?"
                    r"(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(january|february|march|april|may|june|july|august|september|october|november|december)\s*(\d{4})?", re.I)
    for m in rx.finditer(text or ""):
        day, mon, yr = int(m.group(1)), MONTHS[m.group(2).lower()], m.group(3)
        y = int(yr) if yr else TODAY.year
        try:
            d = dt.date(y, mon, day)
        except ValueError:
            continue
        if not yr and d < TODAY - dt.timedelta(days=7):
            d = dt.date(y + 1, mon, day)
        if TODAY <= d <= TODAY + dt.timedelta(days=400):
            return d.isoformat()
    return None


def salary(bs):
    if not isinstance(bs, dict):
        return "Not stated", None
    lo, hi, unit = bs.get("min"), bs.get("max"), bs.get("unitOfWork")
    if not lo and not hi:
        return "Not stated", None
    lo = lo or hi; hi = hi or lo
    if unit == "YEAR":
        s = "£{:,.0f}".format(lo) + ("" if hi == lo else "–£{:,.0f}".format(hi))
        return s, hi
    if unit == "HOUR":
        s = "£{:.2f}".format(lo) + ("" if hi == lo else "–£{:.2f}".format(hi)) + " an hour"
        return s, hi * 1950
    if unit == "MONTH":
        s = "£{:,.0f}".format(lo) + ("" if hi == lo else "–£{:,.0f}".format(hi)) + " a month"
        return s, hi * 12
    if unit == "DAY":
        s = "£{:,.0f}".format(lo) + ("" if hi == lo else "–£{:,.0f}".format(hi)) + " a day"
        return s, hi * 230
    if unit == "WEEK":
        s = "£{:,.0f}".format(lo) + ("" if hi == lo else "–£{:,.0f}".format(hi)) + " a week"
        return s, hi * 52
    return "Not stated", None


START_2027 = re.compile(r"(?:september|sept|summer|autumn|august|july|october)\s+2027|2027\s+(?:intake|start|cohort|graduate|programme|scheme)|start(?:ing|s)?\s+(?:in\s+)?(?:\w+\s+)?2027|join(?:ing)? (?:us )?in (?:\w+ )?2027|2027 graduates", re.I)
SCHEME_TITLE = re.compile(r"graduate (?:scheme|programme|program|development programme|leadership programme|trainee programme)|grad scheme|training contract|2027", re.I)
YEAR_OLD = re.compile(r"\b202[0-6]\b")


def norm_emp(x):
    x = (x or "").lower()
    x = re.sub(r"\(.*?\)", "", x)
    x = re.sub(r"[^a-z0-9 ]", " ", x)
    x = re.sub(r"\b(group|plc|uk|ltd|limited|llp|the|and|co|company|inc|international|services|solicitors)\b", " ", x)
    return re.sub(r"\s+", " ", x).strip()


def tokens(t):
    return set(w for w in re.sub(r"[^a-z0-9 ]", " ", (t or "").lower()).split() if len(w) > 2 and w not in {"graduate", "the", "and", "for", "programme", "scheme", "2027", "london", "manchester", "leeds", "birmingham", "liverpool"})


def from_kaix(x):
    """Map a kaix/indeed-scraper item onto the valig field names used below."""
    if not isinstance(x.get("title"), dict):
        return x
    sal = x.get("salary") or {}
    per = {"yearly": "YEAR", "hourly": "HOUR", "monthly": "MONTH", "daily": "DAY", "weekly": "WEEK"}.get(sal.get("period") or "", None)
    lo = sal.get("min") if sal.get("min") is not None else sal.get("exact")
    hi = sal.get("max") if sal.get("max") is not None else sal.get("exact")
    urls = x.get("urls") or {}
    ext = urls.get("external") or (x.get("apply") or {}).get("url") or ""
    if "indeed.com" in ext:
        ext = ""
    cls = x.get("classification") or {}
    attrs = dict((cls.get("attributes") or {}).get("all") or {})
    req = x.get("requirements") or {}
    for q in (req.get("qualifications") or []) + (req.get("certifications") or []):
        lab = q.get("label") if isinstance(q, dict) else q
        if lab:
            attrs["q-" + str(lab)] = lab
    jt = cls.get("jobType") or []
    return {
        "key": x.get("id"),
        "title": (x.get("title") or {}).get("text"),
        "jobUrl": ext,
        "url": urls.get("indeed"),
        "datePublished": (x.get("dates") or {}).get("posted"),
        "expirationDate": None,
        "validThrough": (x.get("dates") or {}).get("validThrough"),
        "employer.name": (x.get("company") or {}).get("name"),
        "location.city": (x.get("location") or {}).get("city"),
        "baseSalary": {"min": lo, "max": hi, "unitOfWork": per, "currencyCode": sal.get("currency")},
        "description.text": (x.get("description") or {}).get("text") or x.get("snippet") or "",
        "attributes": attrs,
        "occupations": cls.get("occupations") or {},
        "jobTypes": {str(n): (j.get("label") if isinstance(j, dict) else j) for n, j in enumerate(jt)},
    }


def from_linkedin(x):
    """Map a valig/linkedin-jobs-scraper item onto the same field names."""
    if "companyName" not in x or "postedDate" not in x:
        return x
    loc = (x.get("location") or "").split(",")[0].strip()
    loc = re.sub(r"\s+Area$", "", loc)
    sal = x.get("salary") or ""
    bs = {"min": None, "max": None, "unitOfWork": None}
    m = re.findall(r"£([\d,]+(?:\.\d+)?)", sal)
    if m:
        vals = [float(v.replace(",", "")) for v in m]
        bs = {"min": min(vals), "max": max(vals), "unitOfWork": "HOUR" if "/hr" in sal else "YEAR" if "/yr" in sal else None}
    ext = x.get("applyUrl") or ""
    attrs = {}
    if x.get("experienceLevel") in ("Entry level", "Internship"):
        attrs["lvl"] = "Entry level"
    return {"key": "li" + str(x.get("id")), "title": x.get("title"), "jobUrl": ext if ext.startswith("https://") and "linkedin.com" not in ext else "",
            "url": x.get("url"), "datePublished": (x.get("postedDate") or "")[:10], "employer.name": x.get("companyName"),
            "location.city": loc, "baseSalary": bs, "description.text": x.get("description") or "", "attributes": attrs,
            "occupations": {"s": x.get("sector") or ""}, "jobTypes": {"t": x.get("contractType") or ""},
            "linkedinLevel": x.get("experienceLevel")}


def build_role(i, stats):
    i = from_linkedin(from_kaix(i))
    title = (i.get("title") or "").strip()
    emp = (i.get("employer.name") or (i.get("employer") or {}).get("name") or "").strip()
    city_raw = i.get("location.city") or (i.get("location") or {}).get("city")
    text = i.get("description.text") or (i.get("description") or {}).get("text") or ""
    attrs = list((i.get("attributes") or {}).values())
    occ = " ".join((i.get("occupations") or {}).values())
    jtypes = list((i.get("jobTypes") or {}).values())
    title = re.sub(r"[^\w\s&/(),.:'’+#@!?–—-]", "", title).strip(" -–")
    if re.search(r"^(targetjobs|bright network|gradcracker|milkround|prospects|indeed|tiptopjob|jobsite|reed|totaljobs|cv-library|graduate-jobs|higherin|grb|inspiring interns)\b", emp, re.I):
        stats["deny"] += 1; return None
    if not title or not emp or not i.get("key"):
        stats["missing"] += 1; return None
    city = map_city(city_raw)
    if not city:
        stats["city"] += 1; return None
    if DENY_TITLE.search(title):
        stats["deny"] += 1; return None
    if re.search(r"solicitor|lawyer|barrister|chartered|qualified|accredited|\bnqt\b|\bect\b", title, re.I) and not re.search(r"trainee|graduate|apprentice|training contract|paralegal", title, re.I):
        stats["deny"] += 1; return None
    if TRADE_ENG.search(title) and not re.search(r"graduate", title, re.I):
        stats["deny"] += 1; return None
    if re.search(r"\bteacher\b", title, re.I) and not re.search(r"trainee|unqualified|graduate|cover supervisor|teaching assistant", title, re.I):
        stats["deny"] += 1; return None
    if MANAGER.search(title) and not re.search(r"graduate|trainee|junior|assistant (?!manager)|management trainee", title, re.I):
        stats["manager"] += 1; return None
    if not PROF_WORD.search(title):
        stats["notprof"] += 1; return None
    if jtypes and all(j in ("Part-time", "Temporary", "Casual", "Internship", "Apprenticeship") for j in jtypes):
        stats["parttime"] += 1; return None
    yrs = min_years(text)
    is_entry_title = bool(ENTRY_WORD.search(title)) or i.get("linkedinLevel") == "Entry level"
    if i.get("linkedinLevel") in ("Mid-Senior level", "Director", "Executive"):
        stats["experience"] += 1; return None
    if yrs is not None and yrs >= 2:
        stats["experience"] += 1; return None
    if PQE_RE.search(text) and not re.search(r"trainee|paralegal|assistant", title, re.I):
        stats["experience"] += 1; return None
    sal, annual = salary(i.get("baseSalary"))
    bs = i.get("baseSalary") or {}
    if bs.get("unitOfWork") == "HOUR" and (bs.get("max") or bs.get("min") or 99) < 14 and not re.search(r"graduate|teaching|learning support|research", title, re.I):
        stats["lowpay"] += 1; return None
    if annual is not None and annual < 21000:
        stats["lowpay"] += 1; return None
    if annual is not None and annual > 40000 and re.search(r"research", title, re.I):
        stats["highpay"] += 1; return None
    if annual is not None and annual > 75000 and not is_entry_title:
        stats["highpay"] += 1; return None
    if not is_entry_title:
        # roles without an entry word must say so in the ad
        if not re.search(r"no (?:previous |prior )?experience (?:is )?(?:needed|required|necessary)|entry[- ]level|graduates? (?:welcome|are welcome|encouraged)|recent graduate|"
                         r"ideal for (?:a )?graduate|perfect for (?:a )?(?:recent )?graduate|first step in your career|start your career|kick-?start your career|"
                         r"launch your career|early careers|graduate opportunity|full training (?:is )?provided|no experience", text, re.I):
            plain_ok = (yrs is None and not EXP_REQUIRED.search(text) and annual is not None and annual <= 33000
                        and re.search(r"administrator|co-?ordinator|executive|officer|analyst|advis|adviser|negotiator|consultant|researcher|designer|"
                                      r"technician|scientist|paralegal|surveyor|planner|buyer|recruit|caseworker|support worker", title, re.I))
            if not plain_ok:
                stats["notentry"] += 1; return None
    area = classify(title, occ)
    if not area:
        stats["noarea"] += 1; return None
    posted = (i.get("datePublished") or i.get("dateOnIndeed") or "")[:10]
    try:
        pdate = dt.date.fromisoformat(posted)
    except ValueError:
        pdate = TODAY
        posted = TODAY.isoformat()
    scheme = bool(SCHEME_TITLE.search(title)) or bool(START_2027.search(text) and re.search(r"graduate|trainee", title, re.I))
    if scheme and YEAR_OLD.search(title) and "2027" not in title:
        scheme = False
    age = (TODAY - pdate).days
    if age > (MAX_AGE_SCHEME if scheme else MAX_AGE_JOB):
        stats["old"] += 1; return None
    dl = deadline(text, i.get("expirationDate"))
    vt = (i.get("validThrough") or "")[:10]
    if not dl and re.match(r"\d{4}-\d{2}-\d{2}$", vt) and TODAY.isoformat() <= vt <= (TODAY + dt.timedelta(days=400)).isoformat():
        dl = vt
    url = i.get("jobUrl") or ""
    if not url.startswith("https://") or len(url) > 600 or re.search(r"[\s\"'<>]", url):
        url = i.get("url") or ""
    if not url.startswith("https://"):
        stats["nourl"] += 1; return None
    via_emp = url != i.get("url")
    gm, ge = gcse(text)
    lic = licence(text, attrs)
    dmin = degree_min(text)
    um = ucas_min(text)
    al = alevels(text)
    degree_needed = "Bachelor's degree" in attrs or "Master's degree" in attrs or bool(re.search(r"degree (?:is )?(?:required|essential)|(?:require|need|must have|must hold)[^.]{0,40}degree|degree[- ]educated|graduate calibre", text, re.I))
    no_degree = "No degree" in attrs or bool(re.search(r"no degree|degree (?:is )?not (?:required|essential|necessary)", text, re.I))
    bits = []
    if dmin:
        bits.append(dmin + " degree")
    elif degree_needed and not no_degree:
        bits.append("Degree asked for")
    elif no_degree:
        bits.append("No degree needed")
    if um:
        bits.append(f"{um} UCAS")
    if al:
        bits.append(f"{al} at A-level")
    if gm or ge:
        bits.append("GCSE " + " & ".join(x for x in [f"Maths {gm}" if gm else "", f"English {ge}" if ge else ""] if x))
    if lic:
        bits.append("Driving licence")
    role = {
        "id": "in-" + i["key"],
        "type": "scheme" if scheme else "job",
        "emp": emp[:80],
        "title": title[:140],
        "url": url,
        "src": (("Employer site (found on LinkedIn)" if via_emp else "LinkedIn job ad") if str(i["key"]).startswith("li") else ("Employer site (found on Indeed)" if via_emp else "Indeed job ad")),
        "disciplines": disciplines(title, area, text),
        "area": area,
        "cities": [city],
        "start": ("2027 (see ad)" if scheme else "As soon as possible"),
        "dl": dl,
        "status": "open",
        "salary": sal,
        "reqText": " · ".join(bits) if bits else "Not stated in the ad",
        "qual": qual(text),
        "posted": posted,
        "checked": TODAY.isoformat(),
    }
    if city_raw and city.lower() not in city_raw.strip().lower():
        role["town"] = city_raw.strip()[:40]
    for k, v in (("degreeMin", dmin), ("ucasMin", um), ("alevels", al), ("gcseMaths", gm), ("gcseEnglish", ge)):
        if v:
            role[k] = v
    if lic:
        role["licence"] = True
    if yrs == 1:
        role["notes"] = "Asks for about a year's experience – check the ad."
    return role


def main(paths):
    out_path = os.path.join(ROOT, "entry.json")
    try:
        old = json.load(open(out_path))["roles"]
    except Exception:
        old = []
    curated = json.load(open(os.path.join(ROOT, "jobs.json")))["roles"]
    cur_idx = {}
    for r in curated:
        cur_idx.setdefault(norm_emp(r["emp"]).split(" ")[0] if norm_emp(r["emp"]) else "", []).append(tokens(r["title"]))
    stats = {k: 0 for k in ["raw", "missing", "city", "deny", "manager", "notprof", "parttime", "experience", "lowpay", "highpay",
                            "notentry", "noarea", "old", "nourl", "curated", "dupe", "kept"]}
    roles = {}
    for r in old:   # keep earlier ads that are still young enough
        try:
            age = (TODAY - dt.date.fromisoformat(r.get("posted", "2000-01-01"))).days
        except ValueError:
            continue
        lim = MAX_AGE_SCHEME if r.get("type") == "scheme" else MAX_AGE_JOB
        if age <= lim and not (r.get("dl") and r["dl"] < TODAY.isoformat()):
            roles[r["id"]] = r
    for p in paths:
        d = json.load(open(p))
        items = d["items"] if isinstance(d, dict) else d
        for i in items:
            stats["raw"] += 1
            r = build_role(i, stats)
            if not r:
                continue
            ek = norm_emp(r["emp"]).split(" ")[0] if norm_emp(r["emp"]) else ""
            tk = tokens(r["title"])
            if any(len(tk & c) / max(1, len(tk | c)) >= 0.6 for c in cur_idx.get(ek, [])):
                stats["curated"] += 1
                continue
            roles[r["id"]] = r
    # collapse the same ad posted for the same employer+title+city (keep the newest)
    best = {}
    for r in roles.values():
        k = (norm_emp(r["emp"]), re.sub(r"[^a-z0-9]", "", r["title"].lower()), r["cities"][0])
        if k not in best or r["posted"] > best[k]["posted"]:
            if k in best:
                stats["dupe"] += 1
            best[k] = r
        else:
            stats["dupe"] += 1
    final = sorted(best.values(), key=lambda r: (r["cities"][0], r["area"], r["emp"].lower(), r["title"].lower()))
    stats["kept"] = len(final)
    json.dump({"app": "GradTrack 2027", "kind": "job-ads", "updated": TODAY.isoformat(), "roles": final},
              open(out_path, "w"), ensure_ascii=False, separators=(",", ":"))
    print(json.dumps(stats))
    return final


if __name__ == "__main__":
    main(sys.argv[1:])
