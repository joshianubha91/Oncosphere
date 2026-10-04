import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

# Updated Official Clarivate Journal Citation Reports (JCR) Impact Factors
JOURNALS = [
    {"ta": "CA Cancer J Clin", "display": "CA: A Cancer Journal for Clinicians", "if": 685.2},
    {"ta": "Nat Rev Clin Oncol", "display": "Nature Reviews Clinical Oncology", "if": 94.6},
    {"ta": "N Engl J Med", "display": "NEJM", "if": 84.5},
    {"ta": "Nat Rev Cancer", "display": "Nature Reviews Cancer", "if": 60.7},
    {"ta": "Nat Med", "display": "Nature Medicine", "if": 58.7},
    {"ta": "Cancer Cell", "display": "Cancer Cell", "if": 56.1},
    {"ta": "Nature", "display": "Nature", "if": 56.1},
    {"ta": "J Hematol Oncol", "display": "Journal of Hematology & Oncology", "if": 47.8},
    {"ta": "Science", "display": "Science", "if": 47.3},
    {"ta": "Nat Biotechnol", "display": "Nature Biotechnology", "if": 46.9},
    {"ta": "Cell", "display": "Cell", "if": 45.1},
    {"ta": "J Clin Oncol", "display": "Journal of Clinical Oncology", "if": 44.7},
    {"ta": "Mol Cancer", "display": "Molecular Cancer", "if": 42.2},
    {"ta": "Lancet Oncol", "display": "The Lancet Oncology", "if": 33.7},
    {"ta": "Cancer Discov", "display": "Cancer Discovery", "if": 29.5},
    {"ta": "Immunity", "display": "Immunity", "if": 25.5},
    {"ta": "Trends Cancer", "display": "Trends in Cancer", "if": 21.6},
    {"ta": "Cell Stem Cell", "display": "Cell Stem Cell", "if": 19.8},
]

MONTH_MAP = {
    "1": "Jan", "01": "Jan", "jan": "Jan", "january": "Jan",
    "2": "Feb", "02": "Feb", "feb": "Feb", "february": "Feb",
    "3": "Mar", "03": "Mar", "mar": "Mar", "march": "Mar",
    "4": "Apr", "04": "Apr", "apr": "Apr", "april": "Apr",
    "5": "May", "05": "May", "may": "May",
    "6": "Jun", "06": "Jun", "jun": "Jun", "june": "Jun",
    "7": "Jul", "07": "Jul", "jul": "Jul", "july": "Jul",
    "8": "Aug", "08": "Aug", "aug": "Aug", "august": "Aug",
    "9": "Sep", "09": "Sep", "sep": "Sep", "september": "Sep",
    "10": "Oct", "oct": "Oct", "october": "Oct",
    "11": "Nov", "nov": "Nov", "november": "Nov",
    "12": "Dec", "dec": "Dec", "december": "Dec"
}

def categorize(text):
    t = text.lower()
    if any(k in t for k in ["car-t", "tcr", "cell therapy", "adoptive cell", "til therapy", "nk cell"]):
        return "Cell Therapy"
    if any(k in t for k in ["adc", "antibody-drug", "inhibitor", "kras", "her2", "egfr", "kinase", "targeted", "small molecule"]):
        return "Targeted & ADCs"
    if any(k in t for k in ["checkpoint", "pd-1", "pdl1", "ctla-4", "bispecific", "immunotherapy", "t-cell engager"]):
        return "Immuno-Oncology"
    if any(k in t for k in ["ctdna", "liquid biopsy", "methylation", "cfdna", "biomarker", "minimal residual disease", "mrd"]):
        return "Liquid Biopsy"
    return "General Oncology"

ta_map = {j["ta"].lower(): j for j in JOURNALS}
journal_terms = " OR ".join([f'"{j["ta"]}"[ta]' for j in JOURNALS])
all_papers = []

for year in [2026, 2025, 2024]:
    print(f"Fetching 100 papers for {year}...")
    search_term = f"({journal_terms}) AND {year}[dp] AND (cancer OR oncology OR tumor OR neoplasm OR carcinoma OR leukemia OR lymphoma)"
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urllib.parse.urlencode({
        "db": "pubmed",
        "term": search_term,
        "retmax": "130",
        "sort": "pub_date",
        "retmode": "json"
    })
    
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    try:
        time.sleep(1)
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode())
    except Exception as e:
        print(f"Search failed for {year}: {e}")
        continue

    ids = data.get("esearchresult", {}).get("idlist", [])
    print(f"Year {year}: retrieved {len(ids)} candidate IDs")
    
    year_papers = []
    for i in range(0, min(len(ids), 120), 40):
        if len(year_papers) >= 100:
            break
        chunk = ids[i:i+40]
        fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?" + urllib.parse.urlencode({
            "db": "pubmed",
            "id": ",".join(chunk),
            "retmode": "xml"
        })
        fetch_req = urllib.request.Request(fetch_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        try:
            time.sleep(1)
            with urllib.request.urlopen(fetch_req, timeout=25) as r:
                root = ET.fromstring(r.read())
        except Exception as e:
            print(f"Batch fetch error: {e}")
            continue

        for article in root.findall(".//PubmedArticle"):
            if len(year_papers) >= 100:
                break
            try:
                medline = article.find("MedlineCitation")
                art = medline.find("Article")
                title = art.findtext("ArticleTitle", "").strip()
                if not title:
                    continue

                medline_ta = medline.findtext("MedlineJournalInfo/MedlineTA", "").strip()
                j_info = ta_map.get(medline_ta.lower())
                if not j_info:
                    for key, val in ta_map.items():
                        if key in medline_ta.lower():
                            j_info = val
                            break
                if not j_info:
                    continue

                abstract_elem = art.find("Abstract")
                abstract = ""
                if abstract_elem is not None:
                    abstract = " ".join([t.strip() for t in abstract_elem.itertext() if t.strip()])
                if not abstract:
                    abstract = "Full abstract available via primary publisher link."

                pub_date = art.find(".//JournalIssue/PubDate")
                raw_m = pub_date.findtext("Month", "").strip().lower() if pub_date is not None else ""
                month = MONTH_MAP.get(raw_m, "")
                if not month:
                    hist_m = article.findtext(".//History/PubMedPubDate[@PubStatus='pubmed']/Month", "").strip().lower()
                    month = MONTH_MAP.get(hist_m, "Oct" if year == 2026 else "Jun")

                authors = []
                alist = art.find("AuthorList")
                if alist is not None:
                    for a in alist.findall("Author")[:3]:
                        last = a.findtext("LastName", "")
                        init = a.findtext("Initials", "")
                        if last:
                            authors.append(f"{last} {init}".strip())
                authors_str = ", ".join(authors) + (" et al." if len(authors) >= 3 else "")

                doi = ""
                for eid in article.findall(".//ArticleId"):
                    if eid.get("IdType") == "doi":
                        doi = eid.text
                        break
                pmid = medline.findtext("PMID")

                year_papers.append({
                    "title": title,
                    "authors": authors_str or "Research Team",
                    "journal": j_info["display"],
                    "impactFactor": j_info["if"],
                    "year": year,
                    "month": month,
                    "field": categorize(title + " " + abstract),
                    "doi": doi or "N/A",
                    "url": f"https://doi.org/{doi}" if doi else f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    "abstract": abstract[:280] + ("..." if len(abstract) > 280 else "")
                })
            except Exception:
                continue

    print(f"Year {year}: successfully saved {len(year_papers)} papers.")
    all_papers.extend(year_papers)

with open("papers.json", "w", encoding="utf-8") as f:
    json.dump(all_papers, f, indent=2, ensure_ascii=False)

print(f"Finished! Total papers written: {len(all_papers)}")
