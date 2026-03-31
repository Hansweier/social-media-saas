"""
Was wir JETZT schon automatisieren können — OHNE dass der Kunde geantwortet hat:

1. Sample-Content für alle Plattformen generieren (zum Vorzeigen)
2. Content-Kalender befüllen
3. DM-Bot testen
4. Image-Prompts für KI-Bilder erstellen

Starten: python automation/generate_sample_content.py
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
import os, json
from datetime import datetime
load_dotenv()

from platforms.instagram.instagram_content import InstagramContent
from platforms.linkedin.linkedin_content import LinkedInContent
from platforms.facebook.facebook_content import FacebookContent
from platforms.tiktok.tiktok_content import TikTokContent
from platforms.twitter.twitter_content import TwitterContent
from bot.content_calendar import ContentCalendar
from bot.dm_handler import DMHandler

api_key = os.getenv("CLAUDE_API_KEY")
OUTPUT_FILE = "automation/sample_content.json"

TOPICS = {
    "instagram": [
        "Warum wir für das DRK klingeln — nicht für uns",
        "Ein Tag im Leben eines Förderkraft-Außendienstlers",
        "Was Door-to-Door Sales mit dem Roten Kreuz zu tun hat",
    ],
    "linkedin": [
        "Wie Förderkraft das DRK dabei unterstützt neue Fördermitglieder zu gewinnen",
        "Direktvertrieb im Non-Profit Bereich — Chancen und Herausforderungen",
        "Wir suchen motivierte Menschen die für eine gute Sache arbeiten wollen",
    ],
    "facebook": [
        "Wusstest du? Jedes neue DRK-Fördermitglied hilft Leben zu retten",
        "Hinter den Kulissen: So läuft eine DRK-Kampagne mit Förderkraft",
        "Wir sind diese Woche in [Stadt] unterwegs — für das Rote Kreuz",
    ],
    "tiktok": [
        "POV: Du klingelst für das Deutsche Rote Kreuz",
        "Was passiert wirklich wenn du die Tür aufmachst",
        "Das verdienst du wirklich bei Förderkraft",
    ],
    "twitter": [
        "Direktvertrieb für Non-Profits ist unterschätzt",
        "Tipp: So überzeugst du Menschen in 90 Sekunden",
        "Warum das DRK auf Außendienst setzt",
    ],
}

def generate_all():
    print("Generiere Sample-Content für alle Plattformen...\n")

    generators = {
        "instagram": InstagramContent(api_key),
        "linkedin":  LinkedInContent(api_key),
        "facebook":  FacebookContent(api_key),
        "tiktok":    TikTokContent(api_key),
        "twitter":   TwitterContent(api_key),
    }

    results = {"generated_at": str(datetime.now()), "platforms": {}}

    for platform, gen in generators.items():
        print(f"[{platform.upper()}] Generiere {len(TOPICS[platform])} Posts...")
        results["platforms"][platform] = []

        for topic in TOPICS[platform]:
            try:
                if platform == "instagram":
                    content = gen.generate_caption(topic)
                elif platform == "linkedin":
                    content = gen.generate_post(topic)
                elif platform == "facebook":
                    content = gen.generate_post(topic)
                elif platform == "tiktok":
                    content = gen.generate_caption(topic)
                elif platform == "twitter":
                    content = gen.generate_tweet(topic)

                results["platforms"][platform].append({
                    "topic": topic,
                    "content": content,
                    "status": "bereit",
                    "created_at": str(datetime.now()),
                })
                print(f"  OK: {topic[:50]}...")
            except Exception as e:
                print(f"  FEHLER: {e}")

    # Speichern
    os.makedirs("automation", exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nFertig! Gespeichert in: {OUTPUT_FILE}")
    print_preview(results)

def generate_image_prompts():
    """Image-Prompts für KI-Bildgeneratoren (DALL-E, Midjourney, Stable Diffusion)"""
    print("\nGeneriere Image-Prompts...\n")

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    topics = [
        "Förderkraft Außendienstler im Gespräch an der Haustür für das DRK",
        "Motiviertes junges Team bei Förderkraft GmbH",
        "DRK Fördermitglied-Werbung — persönlich und direkt",
        "Behind the Scenes: Förderkraft Teammeeting vor dem Einsatz",
    ]

    prompts = []
    for topic in topics:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            messages=[{"role": "user", "content": f"""Erstelle einen präzisen Bildgenerierungs-Prompt für DALL-E / Midjourney zum Thema: {topic}

Stil: Professionell, authentisch, warm — passend für eine seriöse Werbeagentur die für das Deutsche Rote Kreuz arbeitet.
Farben: Rot, Weiß, Dunkelblau als Akzente.
Antworte NUR mit dem englischen Prompt."""}]
        )
        prompt_text = message.content[0].text
        prompts.append({"topic": topic, "prompt": prompt_text})
        print(f"  Prompt: {prompt_text[:80]}...")

    # Speichern
    with open("automation/image_prompts.json", "w", encoding="utf-8") as f:
        json.dump(prompts, f, ensure_ascii=False, indent=2)
    print("\nImage-Prompts gespeichert in: automation/image_prompts.json")

def print_preview(results):
    """Vorschau der generierten Posts"""
    print("\n" + "="*60)
    print("VORSCHAU — Erster Post pro Plattform:")
    print("="*60)
    for platform, posts in results["platforms"].items():
        if posts:
            print(f"\n[{platform.upper()}]")
            print("-"*40)
            print(posts[0]["content"][:300] + "..." if len(posts[0]["content"]) > 300 else posts[0]["content"])

if __name__ == "__main__":
    print("Was soll generiert werden?")
    print("1. Sample Posts für alle Plattformen")
    print("2. Image Prompts für KI-Bilder")
    print("3. Beides")
    choice = input("\nAuswahl (1/2/3): ").strip()

    if choice in ["1", "3"]:
        generate_all()
    if choice in ["2", "3"]:
        generate_image_prompts()
