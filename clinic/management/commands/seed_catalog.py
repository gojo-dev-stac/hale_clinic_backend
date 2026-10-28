from django.core.management.base import BaseCommand

from clinic.models import Product, Treatment

PRODUCTS = [
    {"slug": "3d-skin-health-cleanser", "name": "3D Skin Health Cleanser", "brand": "Dermalogica", "category": "Cleanse", "price": "38.00", "size": "150ml", "image_url": "https://images.unsplash.com/photo-1556228720-195a672e8a03?auto=format&fit=crop&w=800&q=80", "key": ["Sulphate-free", "Removes SPF and light makeup", "pH balanced", "Morning and evening"], "short_description": "A gentle, sulphate-free gel cleanser that removes makeup without stripping the barrier.", "description": "Amino-acid surfactants lift sunscreen, makeup and daily pollution while glycerin and soothing botanicals keep the barrier intact. Suitable for all skin types including sensitised skin.", "approved": True, "featured": True},
    {"slug": "age-bright-clearing-serum", "name": "AGE Bright Clearing Serum", "brand": "Dermalogica", "category": "Treat", "price": "62.00", "size": "30ml", "image_url": "https://images.unsplash.com/photo-1608571423902-eed4a5ad8108?auto=format&fit=crop&w=800&q=80", "key": ["2% salicylic acid", "Niacinamide", "Overnight use", "Congestion and post-blemish marks"], "short_description": "Salicylic acid and niacinamide to keep congestion clear while supporting skin renewal.", "description": "A lightweight overnight serum combining salicylic acid with the AGE Bright complex to promote clearer, brighter skin without the dryness often associated with acid treatments.", "approved": True, "featured": True},
    {"slug": "rapid-reveal-peel", "name": "Rapid Reveal Peel", "brand": "Dermalogica", "category": "Exfoliate", "price": "74.00", "size": "100ml", "image_url": "https://images.unsplash.com/photo-1629198688000-71f23e745b6e?auto=format&fit=crop&w=800&q=80", "key": ["Weekly treatment", "Lactic acid and enzymes", "Brightening", "Do not use with retinol on the same night"], "short_description": "A professional-strength lactic acid peel for at-home use, once weekly.", "description": "Phytolic acid, lactic acid and pumpkin fruit enzyme complex dissolve dulling surface cells to reveal smoother, brighter skin. Use once weekly in the evening, avoiding the eye area.", "approved": True, "featured": True},
    {"slug": "sound-sleep-cream", "name": "Sound Sleep Cocoon", "brand": "Dermalogica", "category": "Hydrate", "price": "56.00", "size": "50ml", "image_url": "https://images.unsplash.com/photo-1598440947619-2c35fc9aa908?auto=format&fit=crop&w=800&q=80", "key": ["Night use", "Time-released hydration", "Motion-activated botanicals", "All skin types"], "short_description": "A nourishing night cream that works with your skin's natural repair rhythm.", "description": "Motion-activated essential oils and a time-released hydration complex support overnight recovery, so skin looks rested by morning.", "approved": True},
    {"slug": "daily-microfoliant", "name": "Daily Microfoliant", "brand": "Dermalogica", "category": "Exfoliate", "price": "46.00", "size": "74g", "image_url": "https://images.unsplash.com/photo-1608248543803-ba4f8c70ae0b?auto=format&fit=crop&w=800&q=80", "key": ["Daily use", "Physical and chemical exfoliation", "Brightening", "Travel-friendly format"], "short_description": "Rice-enzyme powder that polishes daily for a smoother, more even finish.", "description": "Activate with water to create a foam containing salicylic acid, rice bran and botanical brighteners. Gentle enough for morning use, including after in-clinic treatments once cleared.", "approved": True},
    {"slug": "barrier-repair-serum", "name": "Barrier Repair Serum", "brand": "Hale Edit", "category": "Treat", "price": "54.00", "size": "30ml", "image_url": "https://images.unsplash.com/photo-1571781926291-c477ebfd024b?auto=format&fit=crop&w=800&q=80", "key": ["Post-treatment safe", "Ceramides and squalane", "Fragrance free", "Sensitive skin"], "short_description": "Ceramides, squalane and panthenol to rebuild a compromised barrier.", "description": "Formulated for skin recovering from peels, microneedling or over-exfoliation. Layer under moisturiser morning and evening; compatible with all in-clinic protocols once the skin is closed.", "approved": True, "featured": True},
    {"slug": "peptide-complex", "name": "Peptide Complex concentrate", "brand": "Pending review", "category": "Treat", "price": "0.00", "size": "30ml", "image_url": "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?auto=format&fit=crop&w=800&q=80", "key": ["Not available for online purchase", "Clinical review required", "Written response provided"], "short_description": "GHK-Cu and SNAP-8 related product enquiries are held for clinical and regulatory review.", "description": "Not available for online purchase pending clinical and regulatory review.", "approved": False},
    {"slug": "daily-recovery-kit", "name": "Daily Recovery Kit", "brand": "Hale Edit", "category": "Kits", "price": "98.00", "size": "4 pieces", "image_url": "https://images.unsplash.com/photo-1631730359585-38a4935cbec4?auto=format&fit=crop&w=800&q=80", "key": ["Four-step protocol", "Post-treatment safe", "Save £22 versus individual", "Gift-ready packaging"], "short_description": "Cleanse, treat, hydrate and protect — four client-care essentials.", "description": "Our post-treatment protocol in one box: gentle cleanser, barrier serum, recovery moisturiser and SPF 50. Included complimentary with selected in-clinic courses.", "approved": True},
]
TREATMENTS = [
    ("botox", "Botox", "Face", "From £150", "bookable"),
    ("dermal-fillers", "Dermal Fillers", "Face", "From £250", "bookable"),
    ("skin-boosters", "Skin Boosters — Profhilo", "Skin", "From £250", "bookable"),
    ("polynucleotides", "Polynucleotides", "Skin", "From £280", "bookable"),
    ("microneedling", "Microneedling", "Skin", "From £120", "bookable"),
    ("chemical-peels", "Chemical Peels", "Skin", "From £95", "bookable"),
    ("weight-management", "Weight Management", "Wellness", "Consultation £95", "consultation"),
    ("peptides", "GHK-Cu & SNAP-8 Peptides", "Wellness", "Enquiry only", "review"),
    ("consultations", "Consultations & Clinical Triage", "Wellness", "£95", "consultation"),
    ("phone-consultation", "Phone Consultation", "Wellness", "Complimentary", "consultation"),
]


class Command(BaseCommand):
    help = "Seed the shop and treatment catalog from the local Hale Clinic frontend data."

    def handle(self, *args, **options):
        for product_data in PRODUCTS:
            Product.objects.get_or_create(slug=product_data["slug"], defaults={**product_data, "stock": 100, "active": True})
        for slug, name, category, price_display, treatment_status in TREATMENTS:
            Treatment.objects.get_or_create(slug=slug, defaults={"name": name, "category": category, "price_display": price_display, "status": treatment_status, "active": True})
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(PRODUCTS)} products and {len(TREATMENTS)} treatments."))
