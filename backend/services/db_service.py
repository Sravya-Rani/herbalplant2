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
            "uses": "Used for treating respiratory disorders, fever, cough, cold, and stress. Has anti-inflammatory and antioxidant properties.",
            "description": "A sacred plant in Hinduism, known for its medicinal properties."
        },
        {
            "common_name": "Neem",
            "scientific_name": "Azadirachta indica",
            "uses": "Used for treating skin conditions, diabetes, dental care, and as an insecticide. Has antibacterial and antifungal properties.",
            "description": "A versatile medicinal tree native to India."
        },
        {
            "common_name": "Aloe Vera",
            "scientific_name": "Aloe barbadensis",
            "uses": "Used for treating burns, wounds, skin conditions, and digestive issues. Has moisturizing and healing properties.",
            "description": "A succulent plant known for its gel's medicinal properties."
        },
        {
            "common_name": "Turmeric",
            "scientific_name": "Curcuma longa",
            "uses": "Used for treating inflammation, arthritis, digestive issues, and as an antioxidant. Has anti-inflammatory properties.",
            "description": "A spice with powerful medicinal properties."
        },
        {
            "common_name": "Ginger",
            "scientific_name": "Zingiber officinale",
            "uses": "Used for treating nausea, digestive issues, inflammation, and cold. Has anti-inflammatory and antioxidant properties.",
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
