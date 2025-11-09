import logging
from typing import Optional, List
from sqlalchemy.orm import Session
from database.models import Herb, get_db

logger = logging.getLogger(__name__)


def get_herb_by_name(db: Session, common_name: str) -> Optional[Herb]:
    """Get herb by common name."""
    return db.query(Herb).filter(Herb.common_name.ilike(f"%{common_name}%")).first()


def get_herb_by_scientific_name(db: Session, scientific_name: str) -> Optional[Herb]:
    """Get herb by scientific name."""
    return db.query(Herb).filter(Herb.scientific_name.ilike(f"%{scientific_name}%")).first()


def get_herb_by_id(db: Session, herb_id: int) -> Optional[Herb]:
    """Get herb by ID."""
    return db.query(Herb).filter(Herb.id == herb_id).first()


def get_all_herbs(db: Session) -> List[Herb]:
    """Get all herbs from database."""
    return db.query(Herb).all()


def create_herb(
    db: Session,
    common_name: str,
    scientific_name: str,
    uses: str,
    description: Optional[str] = None,
    image_path: Optional[str] = None,
    image_features: Optional[str] = None
) -> Herb:
    """Create a new herb entry in database."""
    herb = Herb(
        common_name=common_name,
        scientific_name=scientific_name,
        uses=uses,
        description=description,
        image_path=image_path,
        image_features=image_features
    )
    db.add(herb)
    db.commit()
    db.refresh(herb)
    logger.info("Created herb: %s", common_name)
    return herb


def update_herb_features(db: Session, herb_id: int, features: str) -> bool:
    """Update image features for a herb."""
    herb = get_herb_by_id(db, herb_id)
    if herb:
        herb.image_features = features
        db.commit()
        logger.info("Updated features for herb ID: %d", herb_id)
        return True
    return False


def init_sample_data():
    """Initialize database with sample herb data."""
    from database.models import get_db
    db = next(get_db())
    
    # Check if data already exists
    if db.query(Herb).count() > 0:
        logger.info("Database already contains data. Skipping initialization.")
        return
    
    # Sample herb data (without features - will be added when images are processed)
    sample_herbs = [
        {
            "common_name": "Tulsi (Holy Basil)",
            "scientific_name": "Ocimum tenuiflorum",
            "uses": "Medical Uses: 1) Respiratory Health - Treats asthma, bronchitis, cough, and cold. Tulsi tea helps clear respiratory passages. 2) Fever Reduction - Acts as a natural antipyretic to reduce fever. 3) Stress and Anxiety - Adaptogenic properties help manage stress and improve mental clarity. 4) Immune Booster - Enhances immunity and helps fight infections. 5) Anti-inflammatory - Reduces inflammation in the body. 6) Antioxidant - Rich in antioxidants that protect against free radicals. 7) Digestive Health - Aids digestion and treats stomach disorders. 8) Skin Care - Applied topically for skin infections and acne. Note: Consult a healthcare professional before using for medical purposes.",
            "description": "A sacred plant in Hinduism, known for its medicinal properties."
        },
        {
            "common_name": "Neem",
            "scientific_name": "Azadirachta indica",
            "uses": "Medical Uses: 1) Skin Conditions - Treats acne, eczema, psoriasis, and fungal infections. Neem oil and paste are applied topically for wound healing. 2) Diabetes Management - Helps lower blood sugar levels. Neem leaf extract is used in traditional medicine. 3) Dental Care - Neem twigs are used as natural toothbrushes. Neem-based toothpaste helps prevent gum disease and cavities. 4) Immune System - Boosts immunity and has antiviral properties. 5) Digestive Health - Treats stomach ulcers and improves digestion. 6) Anti-inflammatory - Reduces inflammation and pain. 7) Antiparasitic - Effective against intestinal worms. 8) Blood Purification - Detoxifies blood and improves overall health. Note: Consult a healthcare professional before using for medical purposes.",
            "description": "A versatile medicinal tree native to India, known as the 'village pharmacy' for its extensive therapeutic properties."
        },
        {
            "common_name": "Aloe Vera",
            "scientific_name": "Aloe barbadensis",
            "uses": "Medical Uses: 1) Skin Healing - Treats burns, wounds, cuts, and sunburns. Aloe gel promotes faster healing and reduces scarring. 2) Skin Conditions - Helps with acne, eczema, psoriasis, and dry skin. Provides natural moisturization. 3) Digestive Health - Aloe juice aids digestion, treats constipation, and soothes stomach ulcers. 4) Oral Health - Reduces plaque and treats gum inflammation when used as mouthwash. 5) Antioxidant - Contains vitamins and antioxidants that support overall health. 6) Wound Care - Applied topically to prevent infection and accelerate healing. 7) Anti-inflammatory - Reduces inflammation and pain. Note: Consult a healthcare professional before using for medical purposes.",
            "description": "A succulent plant known for its gel's medicinal properties."
        },
        {
            "common_name": "Turmeric",
            "scientific_name": "Curcuma longa",
            "uses": "Medical Uses: 1) Anti-inflammatory - Reduces inflammation in conditions like arthritis, joint pain, and muscle soreness. Curcumin is the active compound. 2) Antioxidant - Protects cells from damage and supports overall health. 3) Digestive Health - Improves digestion, treats indigestion, and helps with bloating. 4) Wound Healing - Applied topically to heal wounds and prevent infection. 5) Skin Health - Treats acne, eczema, and improves skin complexion. 6) Brain Health - May improve memory and reduce risk of neurodegenerative diseases. 7) Heart Health - Supports cardiovascular health and may lower cholesterol. 8) Immune Support - Boosts immunity and helps fight infections. Note: Consult a healthcare professional before using for medical purposes.",
            "description": "A spice with powerful medicinal properties, containing curcumin."
        },
        {
            "common_name": "Ginger",
            "scientific_name": "Zingiber officinale",
            "uses": "Medical Uses: 1) Nausea and Vomiting - Effective for motion sickness, morning sickness, and post-surgery nausea. Ginger tea is commonly used. 2) Digestive Health - Relieves indigestion, bloating, and stomach discomfort. Stimulates digestion. 3) Anti-inflammatory - Reduces inflammation and pain, especially in arthritis and muscle soreness. 4) Cold and Flu - Helps treat cold symptoms, sore throat, and congestion. Warming properties. 5) Menstrual Pain - Reduces menstrual cramps and discomfort. 6) Blood Circulation - Improves blood flow and may lower blood pressure. 7) Antioxidant - Contains antioxidants that protect against oxidative stress. 8) Respiratory Health - Helps with cough and respiratory congestion. Note: Consult a healthcare professional before using for medical purposes.",
            "description": "A rhizome used both as spice and medicine."
        },
        {
            "common_name": "Mint",
            "scientific_name": "Mentha",
            "uses": "Used for treating digestive issues, respiratory problems, and as a flavoring agent. Has cooling and soothing properties.",
            "description": "A refreshing herb with multiple uses."
        },
        {
            "common_name": "Coriander",
            "scientific_name": "Coriandrum sativum",
            "uses": "Used for treating digestive issues, inflammation, and as a flavoring agent. Rich in antioxidants.",
            "description": "An aromatic herb used in cooking and medicine."
        },
        {
            "common_name": "Fenugreek",
            "scientific_name": "Trigonella foenum-graecum",
            "uses": "Used for treating diabetes, digestive issues, and increasing milk production in nursing mothers. Rich in fiber and protein.",
            "description": "A herb with seeds used in cooking and medicine."
        },
        {
            "common_name": "Cumin",
            "scientific_name": "Cuminum cyminum",
            "uses": "Used for treating digestive issues, improving immunity, and as a spice. Has antioxidant properties.",
            "description": "A spice with medicinal properties."
        },
        {
            "common_name": "Cardamom",
            "scientific_name": "Elettaria cardamomum",
            "uses": "Used for treating digestive issues, bad breath, and as a flavoring agent. Has antioxidant and anti-inflammatory properties.",
            "description": "A spice known as the queen of spices."
        }
    ]
    
    for herb_data in sample_herbs:
        create_herb(
            db=db,
            common_name=herb_data["common_name"],
            scientific_name=herb_data["scientific_name"],
            uses=herb_data["uses"],
            description=herb_data.get("description")
        )
    
    logger.info("Initialized database with %d sample herbs", len(sample_herbs))
