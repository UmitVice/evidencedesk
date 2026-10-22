"""Fictional products used to synthesize support corpora for distillation.

None of them is RelayNest, the product behind the evaluation set, so the fine-tuned model
is evaluated on a product, tenant, and document set it never saw during training.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Product:
    slug: str
    name: str
    language: str  # "en" or "tr"
    domain: str
    tenants: tuple[str, str]  # (customer that asks, unrelated customer that must stay private)
    split: str = "train"


PRODUCTS: tuple[Product, ...] = (
    Product(
        "ledgerloop", "LedgerLoop", "en",
        "an invoicing and payments API with webhooks, payouts, refunds, and API keys",
        ("Northwind Retail", "Oakline Studios"),
    ),
    Product(
        "vaultkey", "VaultKey Custody", "en",
        "an institutional digital-asset custody platform with withdrawal whitelists, "
        "multi-approval policies, cold storage settlement windows, and audit exports",
        ("Meridian Capital", "Bluefin Fund"),
    ),
    Product(
        "shiptrail", "ShipTrail", "en",
        "a shipment tracking API with carrier events, delivery exceptions, and label exports",
        ("Coastal Goods", "Pinecrest Supply"),
    ),
    Product(
        "peopledesk", "PeopleDesk", "en",
        "an HR platform with leave policies, payroll exports, SSO, and role permissions",
        ("Brightpath Logistics", "Harlow Clinics"),
    ),
    Product(
        "beamline", "Beamline CI", "en",
        "a hosted CI/CD service with runners, build caches, secrets, and deployment gates",
        ("Quanta Labs", "Riverside Games"),
    ),
    Product(
        "mailharbor", "MailHarbor", "en",
        "a transactional email service with domains, bounces, suppression lists, and rate limits",
        ("Fable Books", "Ironwood Legal"),
    ),
    Product(
        "flagforge", "FlagForge", "en",
        "a feature flag service with environments, gradual rollouts, audit logs, and SDK keys",
        ("Lumen Health", "Stackyard"),
        split="validation",
    ),
    Product(
        "atlasx", "Atlas Exchange", "en",
        "a retail crypto exchange with deposits, withdrawals, network fees, identity verification, "
        "and account security",
        ("Customer account 4471", "Customer account 9182"),
    ),
    Product(
        "kasacuzdan", "Kasa Cüzdan", "tr",
        "Türkçe destek dokümanları olan bir kripto cüzdan uygulaması: yatırma, çekme, "
        "ağ ücretleri, kimlik doğrulama ve hesap güvenliği",
        ("Müşteri hesabı 2210", "Müşteri hesabı 7734"),
    ),
    Product(
        "faturabulutu", "Fatura Bulutu", "tr",
        "Türkçe destek dokümanları olan bir e-fatura ve e-arşiv SaaS ürünü: entegrasyon, "
        "API anahtarları, iptal, dışa aktarma ve kullanıcı yetkileri",
        ("Ege Tekstil", "Anka Lojistik"),
        split="validation",
    ),
)
