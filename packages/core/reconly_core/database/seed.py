"""Seed data for default templates and system configuration.

This module provides default PromptTemplates and ReportTemplates that are
created on first run. These are marked as `is_system=True` and have no user_id.
"""
from sqlalchemy.orm import Session
from reconly_core.database.models import PromptTemplate, ReportTemplate


# ═══════════════════════════════════════════════════════════════════════════════
# DEFAULT PROMPT TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_PROMPT_TEMPLATES = [
    {
        "name": "Standard Summary (German)",
        "description": "Default German summarization prompt with structured output",
        "language": "de",
        "target_length": 150,
        "system_prompt": """Du bist ein professioneller Content-Zusammenfasser.
Erstelle präzise, informative Zusammenfassungen auf Deutsch.
Fokussiere dich auf die wichtigsten Informationen und Kernaussagen.
WICHTIG: Wenn der Originaltitel nicht auf Deutsch ist, übersetze ihn ins Deutsche.""",
        "user_prompt_template": """Fasse den folgenden Inhalt einer {source_type} zusammen.

Originaltitel: {title}

Inhalt:
{content}

Erstelle eine prägnante Zusammenfassung mit etwa {target_length} Wörtern:

**Titel:** [Deutscher Titel - übersetze falls nötig]

1. **Hauptthema** (1-2 Sätze): Worum geht es?
2. **Wichtigste Punkte** (3-5 Stichpunkte): Was sind die Kernaussagen?
3. **Fazit** (1-2 Sätze): Was ist die Haupterkenntnis?

Die Zusammenfassung sollte informativ und leicht verständlich sein.""",
    },
    {
        "name": "Standard Summary (English)",
        "description": "Default English summarization prompt with structured output",
        "language": "en",
        "target_length": 150,
        "system_prompt": """You are a professional content summarizer.
Create concise, informative summaries in English.
Focus on the most important information and key takeaways.
IMPORTANT: If the original title is not in English, translate it to English.""",
        "user_prompt_template": """Summarize the following content from a {source_type}.

Original Title: {title}

Content:
{content}

IMPORTANT: You MUST follow this exact output format with approximately {target_length} words:

**Title:** [Write the English title here - translate from original if not English]

**Main Topic:** [1-2 sentences: What is this about?]

**Key Points:**
- [Point 1]
- [Point 2]
- [Point 3]

**Conclusion:** [1-2 sentences: What is the key insight?]

CRITICAL: Start your response with "**Title:**" followed by the translated English title.""",
    },
    {
        "name": "Quick Brief (German)",
        "description": "Ultra-short German summary for quick scanning",
        "language": "de",
        "target_length": 50,
        "system_prompt": """Du bist ein Content-Zusammenfasser für Eilige.
Erstelle extrem kurze, prägnante Zusammenfassungen auf Deutsch.
Übersetze Titel ins Deutsche falls nötig.""",
        "user_prompt_template": """Fasse den folgenden Inhalt in maximal {target_length} Wörtern zusammen.

Titel: {title}

Inhalt:
{content}

**Titel:** [Deutscher Titel]
Antworte in 2-3 Sätzen: Was ist die Kernaussage?""",
    },
    {
        "name": "Quick Brief (English)",
        "description": "Ultra-short English summary for quick scanning",
        "language": "en",
        "target_length": 50,
        "system_prompt": """You are a content summarizer for busy readers.
Create extremely short, concise summaries in English.
Translate title to English if needed.""",
        "user_prompt_template": """Summarize the following content in at most {target_length} words.

Title: {title}

Content:
{content}

**Title:** [English title]
Answer in 2-3 sentences: What is the key takeaway?""",
    },
    {
        "name": "Deep Analysis (German)",
        "description": "Detailed German analysis with context and implications",
        "language": "de",
        "target_length": 300,
        "system_prompt": """Du bist ein erfahrener Analyst und Content-Experte.
Erstelle tiefgehende Analysen mit Kontext und Einordnung auf Deutsch.
Berücksichtige Implikationen und mögliche Auswirkungen.
WICHTIG: Wenn der Originaltitel nicht auf Deutsch ist, übersetze ihn ins Deutsche.""",
        "user_prompt_template": """Analysiere den folgenden Inhalt einer {source_type} ausführlich.

Originaltitel: {title}

Inhalt:
{content}

Erstelle eine detaillierte Analyse mit etwa {target_length} Wörtern:

**Titel:** [Deutscher Titel - übersetze falls nötig]

1. **Zusammenfassung** (2-3 Sätze): Worum geht es?
2. **Kontext** (2-3 Sätze): Warum ist das relevant?
3. **Hauptargumente/Erkenntnisse** (5-7 Punkte): Was sind die zentralen Aussagen?
4. **Kritische Einordnung** (2-3 Sätze): Was sind Stärken/Schwächen?
5. **Implikationen** (2-3 Sätze): Was bedeutet das für die Zukunft?
6. **Fazit** (1-2 Sätze): Was ist die wichtigste Erkenntnis?""",
    },
    {
        "name": "Deep Analysis (English)",
        "description": "Detailed English analysis with context and implications",
        "language": "en",
        "target_length": 300,
        "system_prompt": """You are an experienced analyst and content expert.
Create in-depth analyses with context and implications in English.
Consider broader impact and future relevance.
IMPORTANT: If the original title is not in English, translate it to English.""",
        "user_prompt_template": """Analyze the following content from a {source_type} in detail.

Original Title: {title}

Content:
{content}

Create a detailed analysis of approximately {target_length} words:

**Title:** [English title - translate if needed]

1. **Summary** (2-3 sentences): What is this about?
2. **Context** (2-3 sentences): Why is this relevant?
3. **Key Arguments/Findings** (5-7 points): What are the central claims?
4. **Critical Assessment** (2-3 sentences): What are the strengths/weaknesses?
5. **Implications** (2-3 sentences): What does this mean for the future?
6. **Conclusion** (1-2 sentences): What is the most important insight?""",
    },
    {
        "name": "Equity Analyst Brief (German)",
        "description": "SAP-style daily analyst morning brief with sections and ratings (use with all_sources digest mode)",
        "language": "de",
        "target_length": 600,
        "system_prompt": """Du bist ein Senior Equity Research Analyst für institutionelle Investoren.

KRITISCHE GENAUIGKEITSREGELN - UNBEDINGT BEFOLGEN:
1. Berichte NUR Informationen, die EXPLIZIT in den bereitgestellten Artikeln stehen
2. NIEMALS Finanzzahlen erfinden (Umsatz, Gewinn, Margen, Kurse, Kursziele)
3. NIEMALS Analystenbewertungen, Kursziele oder Konsensschätzungen erfinden
4. NIEMALS Partnerschaften, Produktankündigungen oder strategische Maßnahmen erfinden
5. Wenn Information für einen Abschnitt NICHT in den Artikeln steht: "Keine Berichterstattung in heutigen Quellen"
6. IMMER die Quelle zitieren: "Laut [Quelle]..." oder "(Quelle: X)"
7. Bei mehrdeutigen Überschriften konservativ berichten, nicht ausschmücken

Formatierungsregeln:
- Emoji-Nummern für Abschnitte (1️⃣, 2️⃣, etc.)
- Bewertungsrelevanz: 🔴 (hoch/kurskritisch), 🟡 (mittel), ❌ (keine)
- Beginne mit 🔴 Executive Summary (30 Sekunden)
- Ende mit 📊 Analysten-Fazit

Präzise schreiben, Quellen zitieren, niemals erfinden.""",
        "user_prompt_template": """Analysiere NUR die folgenden {item_count} Artikel aus {source_count} Quellen.

{articles}

WICHTIG: Basiere deinen Brief NUR auf den obigen Artikeln. Füge KEINE Informationen aus deinem Trainingswissen hinzu.

Erstelle einen Analyst Morning Brief mit diesen Abschnitten:

🔴 Executive Summary (30 Sekunden)
- 3-4 Bullet Points zu Entwicklungen, die TATSÄCHLICH in den Artikeln erwähnt werden
- Jeder Punkt muss die Quelle zitieren: "(Quelle: X)"
- Gesamtbewertung NUR basierend auf dem, was die Artikel sagen

1️⃣ Unternehmensspezifische News
- NUR News berichten, die explizit in obigen Artikeln stehen
- Falls keine: "Keine Berichterstattung in heutigen Quellen"
- Quelle für jeden Fakt zitieren
- Bewertungsrelevanz: 🔴/🟡/❌

2️⃣ Strategische & Produkt-News
- NUR Ankündigungen berichten, die explizit in den Artikeln stehen
- Falls keine: "Keine Berichterstattung in heutigen Quellen"
- Quelle für jeden Fakt zitieren
- Bewertungsrelevanz: 🔴/🟡/❌

3️⃣ Peer- & Wettbewerbs-Update
- Wettbewerber NUR erwähnen, wenn sie in den Artikeln vorkommen
- Falls keine: "Keine Berichterstattung in heutigen Quellen"
- Bewertungsrelevanz: 🔴/🟡/❌

4️⃣ Analysten & Konsensbewegungen
- NUR berichten, wenn Analystenaktionen explizit erwähnt werden
- NIEMALS Kursziele oder Ratings erfinden
- Falls keine: "Keine Berichterstattung in heutigen Quellen"
- Bewertungsrelevanz: 🔴/🟡/❌

5️⃣ Makro & FX
- NUR berichten, wenn Makro-/FX-Daten in den Artikeln stehen
- NIEMALS Wechselkurse oder Wirtschaftszahlen erfinden
- Falls keine: "Keine Berichterstattung in heutigen Quellen"
- Bewertungsrelevanz: 🔴/🟡/❌

6️⃣ Markt & Trading-Signale
- NUR Handelsdaten berichten, wenn explizit in Artikeln
- Falls keine: "Keine Berichterstattung in heutigen Quellen"
- Bewertungsrelevanz: 🔴/🟡/❌

📊 Analysten-Fazit
- NUR zusammenfassen, was die Artikel tatsächlich berichten
- Ehrlich über Lücken: "Heutige Quellen deckten X, Y, Z nicht ab"

Zielumfang: {target_length} Wörter. Genauigkeit vor Vollständigkeit - leere Abschnitte sind besser als erfundene Inhalte.""",
    },
    {
        "name": "Equity Analyst Brief (English)",
        "description": "Daily analyst morning brief with sections and ratings (use with all_sources digest mode)",
        "language": "en",
        "target_length": 600,
        "system_prompt": """You are a Senior Equity Research Analyst creating morning briefs for institutional investors.

CRITICAL ACCURACY RULES - YOU MUST FOLLOW THESE:
1. ONLY report information that is EXPLICITLY stated in the provided articles
2. NEVER invent, fabricate, or extrapolate financial figures (revenue, profit, margins, prices)
3. NEVER make up analyst ratings, target prices, or consensus estimates
4. NEVER fabricate partnerships, product announcements, or strategic moves
5. If information for a section is NOT in the articles, write "No coverage in today's sources"
6. ALWAYS cite the source name when reporting a fact: "According to [Source]..." or "(Source: X)"
7. If an article headline is ambiguous, report it conservatively without embellishment

Formatting rules:
- Use emoji numbers for sections (1️⃣, 2️⃣, etc.)
- Valuation relevance per section: 🔴 (high/price-critical), 🟡 (medium), ❌ (none)
- Start with 🔴 Executive Summary (30 seconds reading time)
- End with 📊 Analyst Conclusion

Write precisely, cite sources, never fabricate.""",
        "user_prompt_template": """Analyze ONLY the following {item_count} articles from {source_count} sources.

{articles}

IMPORTANT: Base your brief ONLY on the articles above. Do NOT add information from your training data.

Create an Analyst Morning Brief with these sections:

🔴 Executive Summary (30 seconds)
- 3-4 bullet points of developments ACTUALLY mentioned in the articles
- Each point must cite its source: "(Source: X)"
- Overall assessment based ONLY on what the articles say

1️⃣ Company-Specific News
- ONLY report news explicitly mentioned in articles above
- If no company news in sources, write: "No coverage in today's sources"
- Cite source for each fact
- Valuation relevance: 🔴/🟡/❌

2️⃣ Strategic & Product News
- ONLY report announcements explicitly in the articles
- If none, write: "No coverage in today's sources"
- Cite source for each fact
- Valuation relevance: 🔴/🟡/❌

3️⃣ Peer & Competition Update
- ONLY mention competitors if they appear in the articles
- If none, write: "No coverage in today's sources"
- Valuation relevance: 🔴/🟡/❌

4️⃣ Analyst & Consensus Movements
- ONLY report if analyst actions are explicitly mentioned
- NEVER invent target prices or ratings
- If none, write: "No coverage in today's sources"
- Valuation relevance: 🔴/🟡/❌

5️⃣ Macro & FX
- ONLY report if macro/FX data is in the articles
- NEVER invent exchange rates or economic figures
- If none, write: "No coverage in today's sources"
- Valuation relevance: 🔴/🟡/❌

6️⃣ Market & Trading Signals
- ONLY report trading data if explicitly in articles
- If none, write: "No coverage in today's sources"
- Valuation relevance: 🔴/🟡/❌

📊 Analyst Conclusion
- Summarize ONLY what the articles actually report
- Be honest about gaps: "Today's sources did not cover X, Y, Z"

Target length: {target_length} words. Accuracy over completeness - empty sections are better than fabricated content.""",
    },
    {
        "name": "Consolidated Summary (German)",
        "description": "Default German template for consolidated digests (per_source or all_sources mode)",
        "language": "de",
        "target_length": 300,
        "system_prompt": """Du bist ein Content-Synthesizer. Erstelle zusammenhängende
Briefings, die Informationen aus mehreren Artikeln kombinieren.

WICHTIG: Verwende Markdown-Links für Quellenangaben im Format [Quellenname](URL).
Beispiele:
- "Laut [Bloomberg](https://example.com/article1)..."
- "[Reuters](https://example.com/article2) berichtet..."

Synthetisiere Erkenntnisse, anstatt nur zu aggregieren.""",
        "user_prompt_template": """Erstelle ein zusammenfassendes Briefing aus den folgenden {item_count} Artikeln.

{articles}

Erstelle eine kohärente Zusammenfassung mit etwa {target_length} Wörtern, die:
1. Die wichtigsten gemeinsamen Themen identifiziert
2. Chronologische Entwicklungen aufzeigt (falls relevant)
3. Kernaussagen und Trends herausarbeitet
4. Quellenangaben als Markdown-Links formatiert: [Quellenname](URL)

Die Zusammenfassung sollte wie ein professionelles Briefing klingen, nicht wie eine Auflistung.""",
    },
    {
        "name": "Consolidated Summary (English)",
        "description": "Default English template for consolidated digests (per_source or all_sources mode)",
        "language": "en",
        "target_length": 300,
        "system_prompt": """You are a content synthesizer. Create cohesive briefings
that combine information from multiple articles.

IMPORTANT: Use markdown links for source citations in format [Source Name](URL).
Examples:
- "According to [Bloomberg](https://example.com/article1)..."
- "[Reuters](https://example.com/article2) reports..."

Synthesize insights rather than just aggregating.""",
        "user_prompt_template": """Create a consolidated briefing from the following {item_count} articles.

{articles}

Create a cohesive summary of approximately {target_length} words that:
1. Identifies the key common themes
2. Shows chronological developments (if relevant)
3. Highlights core messages and trends
4. Formats source citations as markdown links: [Source Name](URL)

The summary should read like a professional briefing, not a list.""",
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# DEFAULT REPORT TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_REPORT_TEMPLATES = [
    {
        "name": "Daily Digest (Markdown)",
        "description": "Clean Markdown format for daily digest emails or notes",
        "format": "markdown",
        "template_content": """# {{ feed.name }} - Daily Digest

**Generated:** {{ generated_at.strftime('%Y-%m-%d %H:%M') }}
{% if run_info %}
**Sources processed:** {{ run_info.sources_processed }} | **Items:** {{ run_info.items_processed }}
{% endif %}

---

{% for digest in digests %}
## {{ digest.title }}

{% if digest.author %}*By {{ digest.author }}*{% endif %}
{% if digest.published_at %}| *{{ digest.published_at.strftime('%Y-%m-%d') }}*{% endif %}

{{ digest.summary }}

🔗 [Read more]({{ digest.url }})

---

{% endfor %}

*Generated by Reconly*
""",
    },
    {
        "name": "Daily Digest (HTML Email)",
        "description": "Styled HTML format for email newsletters",
        "format": "html",
        "template_content": """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ feed.name }} - Daily Digest</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }
    .header { border-bottom: 2px solid #4a90d9; padding-bottom: 10px; margin-bottom: 20px; }
    .header h1 { margin: 0; color: #4a90d9; }
    .meta { color: #666; font-size: 0.9em; }
    .digest-item { margin-bottom: 25px; padding-bottom: 20px; border-bottom: 1px solid #eee; }
    .digest-item h2 { margin: 0 0 10px 0; font-size: 1.2em; }
    .digest-item h2 a { color: #333; text-decoration: none; }
    .digest-item h2 a:hover { color: #4a90d9; }
    .digest-meta { color: #888; font-size: 0.85em; margin-bottom: 10px; }
    .summary { color: #444; }
    .read-more { display: inline-block; margin-top: 10px; color: #4a90d9; text-decoration: none; }
    .footer { margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; color: #888; font-size: 0.85em; text-align: center; }
  </style>
</head>
<body>
  <div class="header">
    <h1>{{ feed.name }}</h1>
    <p class="meta">Daily Digest &bull; {{ generated_at.strftime('%B %d, %Y') }}</p>
  </div>

  {% for digest in digests %}
  <div class="digest-item">
    <h2><a href="{{ digest.url }}">{{ digest.title }}</a></h2>
    <p class="digest-meta">
      {% if digest.author %}{{ digest.author }} &bull; {% endif %}
      {% if digest.published_at %}{{ digest.published_at.strftime('%Y-%m-%d') }} &bull; {% endif %}
      {{ digest.source_type }}
    </p>
    <p class="summary">{{ digest.summary }}</p>
    <a href="{{ digest.url }}" class="read-more">Read full article →</a>
  </div>
  {% endfor %}

  <div class="footer">
    <p>Generated by Reconly</p>
    {% if run_info %}
    <p>{{ run_info.sources_processed }} sources &bull; {{ run_info.items_processed }} items processed</p>
    {% endif %}
  </div>
</body>
</html>
""",
    },
    {
        "name": "Simple List (Markdown)",
        "description": "Minimal list format for quick reference",
        "format": "markdown",
        "template_content": """# {{ feed.name }}

{{ generated_at.strftime('%Y-%m-%d') }}

{% for digest in digests %}
- **[{{ digest.title }}]({{ digest.url }})** {% if digest.author %}({{ digest.author }}){% endif %}
  {{ digest.summary | truncate(200) }}

{% endfor %}
""",
    },
    {
        "name": "Obsidian Note",
        "description": "Markdown format optimized for Obsidian with frontmatter",
        "format": "markdown",
        "template_content": """---
title: "{{ feed.name }} - {{ generated_at.strftime('%Y-%m-%d') }}"
date: {{ generated_at.strftime('%Y-%m-%d') }}
type: digest
feed: "{{ feed.name }}"
tags:
  - digest
  - automated
{% if run_info %}
sources_processed: {{ run_info.sources_processed }}
items_processed: {{ run_info.items_processed }}
{% endif %}
---

# {{ feed.name }}

> [!info] Generated
> {{ generated_at.strftime('%Y-%m-%d %H:%M') }}

{% for digest in digests %}
## {{ digest.title }}

> [!quote] Summary
> {{ digest.summary }}

- **Source:** {{ digest.source_type }}
{% if digest.author %}- **Author:** {{ digest.author }}{% endif %}
{% if digest.published_at %}- **Published:** {{ digest.published_at.strftime('%Y-%m-%d') }}{% endif %}
- **Link:** [{{ digest.url | truncate(50) }}]({{ digest.url }})

---

{% endfor %}
""",
    },
    {
        "name": "JSON Export",
        "description": "Machine-readable JSON format for integrations",
        "format": "text",
        "template_content": """{
  "feed": {
    "name": "{{ feed.name }}",
    "id": {{ feed.id }}
  },
  "generated_at": "{{ generated_at.isoformat() }}",
  {% if run_info %}
  "run_info": {
    "sources_processed": {{ run_info.sources_processed }},
    "items_processed": {{ run_info.items_processed }},
    "total_cost": {{ run_info.total_cost }}
  },
  {% endif %}
  "digests": [
    {% for digest in digests %}
    {
      "id": {{ digest.id }},
      "title": "{{ digest.title | replace('"', '\\"') }}",
      "url": "{{ digest.url }}",
      "source_type": "{{ digest.source_type }}",
      "author": {% if digest.author %}"{{ digest.author | replace('"', '\\"') }}"{% else %}null{% endif %},
      "published_at": {% if digest.published_at %}"{{ digest.published_at.isoformat() }}"{% else %}null{% endif %},
      "summary": "{{ digest.summary | replace('"', '\\"') | replace('\n', '\\n') }}"
    }{% if not loop.last %},{% endif %}
    {% endfor %}
  ]
}
""",
    },
    {
        "name": "Analyst Morning Brief (Markdown)",
        "description": "Professional equity analyst daily brief format (use with all_sources digest mode)",
        "format": "markdown",
        "template_content": """{{ feed.name }} – Daily Analyst Morning Brief

Date: {{ generated_at.strftime('%Y-%m-%d') }}
Ticker: {{ feed.name.split()[0] if ' ' in feed.name else feed.name }}
Bias: ⚖️ Neutral
Time Horizon: 3–12 months

{% for digest in digests %}
{{ digest.summary }}
{% endfor %}

---

*Sources processed: {{ run_info.sources_processed if run_info else 'N/A' }} | Articles analyzed: {{ run_info.items_processed if run_info else 'N/A' }}*
*Generated: {{ generated_at.strftime('%Y-%m-%d %H:%M') }} | Reconly*
""",
    },
    {
        "name": "Analyst Morning Brief (HTML)",
        "description": "Professional equity analyst daily brief in HTML format (use with all_sources digest mode)",
        "format": "html",
        "template_content": """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ feed.name }} – Analyst Brief</title>
  <style>
    body { font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.5; color: #1a1a1a; max-width: 700px; margin: 0 auto; padding: 20px; background: #f8f9fa; }
    .header { background: linear-gradient(135deg, #1e3a5f 0%, #2c5282 100%); color: white; padding: 24px; border-radius: 8px 8px 0 0; margin-bottom: 0; }
    .header h1 { margin: 0 0 8px 0; font-size: 1.5em; font-weight: 600; }
    .header .meta { opacity: 0.9; font-size: 0.9em; }
    .header .ticker { background: rgba(255,255,255,0.2); padding: 4px 12px; border-radius: 4px; display: inline-block; margin-top: 12px; font-weight: 500; }
    .content { background: white; padding: 24px; border-radius: 0 0 8px 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
    .summary { white-space: pre-wrap; font-size: 0.95em; }
    .section-header { color: #2c5282; font-weight: 600; margin-top: 20px; }
    .rating-high { color: #c53030; }
    .rating-medium { color: #d69e2e; }
    .rating-none { color: #718096; }
    .footer { margin-top: 24px; padding-top: 16px; border-top: 1px solid #e2e8f0; color: #718096; font-size: 0.85em; text-align: center; }
    .stats { display: flex; gap: 16px; justify-content: center; margin-bottom: 8px; }
    .stat { background: #edf2f7; padding: 4px 12px; border-radius: 4px; }
  </style>
</head>
<body>
  <div class="header">
    <h1>{{ feed.name }}</h1>
    <div class="meta">Daily Analyst Morning Brief • {{ generated_at.strftime('%Y-%m-%d') }}</div>
    <div class="ticker">{{ feed.name.split()[0] if ' ' in feed.name else feed.name }}</div>
  </div>

  <div class="content">
    {% for digest in digests %}
    <div class="summary">{{ digest.summary }}</div>
    {% endfor %}
  </div>

  <div class="footer">
    <div class="stats">
      <span class="stat">{{ run_info.sources_processed if run_info else 'N/A' }} Sources</span>
      <span class="stat">{{ run_info.items_processed if run_info else 'N/A' }} Articles</span>
    </div>
    <div>Generated: {{ generated_at.strftime('%Y-%m-%d %H:%M') }} | Reconly</div>
  </div>
</body>
</html>
""",
    },
]


def seed_default_templates(session: Session, force: bool = False) -> dict:
    """
    Seed the database with default PromptTemplates and ReportTemplates.

    Args:
        session: SQLAlchemy database session
        force: If True, recreate templates even if they exist

    Returns:
        Dict with counts of created templates
    """
    result = {
        "prompt_templates_created": 0,
        "report_templates_created": 0,
        "prompt_templates_skipped": 0,
        "report_templates_skipped": 0,
    }

    # Seed PromptTemplates
    for template_data in DEFAULT_PROMPT_TEMPLATES:
        existing = session.query(PromptTemplate).filter(
            PromptTemplate.name == template_data["name"],
            PromptTemplate.origin == 'builtin',
        ).first()

        if existing and not force:
            result["prompt_templates_skipped"] += 1
            continue

        if existing and force:
            session.delete(existing)

        template = PromptTemplate(
            user_id=None,
            origin='builtin',
            **template_data,
        )
        session.add(template)
        result["prompt_templates_created"] += 1

    # Seed ReportTemplates
    for template_data in DEFAULT_REPORT_TEMPLATES:
        existing = session.query(ReportTemplate).filter(
            ReportTemplate.name == template_data["name"],
            ReportTemplate.origin == 'builtin',
        ).first()

        if existing and not force:
            result["report_templates_skipped"] += 1
            continue

        if existing and force:
            session.delete(existing)

        template = ReportTemplate(
            user_id=None,
            origin='builtin',
            **template_data,
        )
        session.add(template)
        result["report_templates_created"] += 1

    session.commit()
    return result


def get_default_prompt_template(session: Session, language: str = "de") -> PromptTemplate | None:
    """Get the default system prompt template for a language."""
    name = f"Standard Summary ({'German' if language == 'de' else 'English'})"
    return session.query(PromptTemplate).filter(
        PromptTemplate.name == name,
        PromptTemplate.origin == 'builtin',
    ).first()


def get_default_report_template(session: Session, format: str = "markdown") -> ReportTemplate | None:
    """Get the default system report template for a format."""
    if format == "html":
        name = "Daily Digest (HTML Email)"
    else:
        name = "Daily Digest (Markdown)"

    return session.query(ReportTemplate).filter(
        ReportTemplate.name == name,
        ReportTemplate.origin == 'builtin',
    ).first()


def get_default_consolidated_template(session: Session, language: str = "de") -> PromptTemplate | None:
    """Get the default system prompt template for consolidated digests."""
    name = f"Consolidated Summary ({'German' if language == 'de' else 'English'})"
    return session.query(PromptTemplate).filter(
        PromptTemplate.name == name,
        PromptTemplate.origin == 'builtin',
    ).first()
