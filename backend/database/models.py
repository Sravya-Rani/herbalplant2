from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from pathlib import Path

# Database setup
BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/database/herbs.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Herb(Base):
    __tablename__ = "herbs"
    
    id = Column(Integer, primary_key=True, index=True)
    common_name = Column(String, nullable=False, index=True)
    scientific_name = Column(String, nullable=False)
    uses = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    image_path = Column(String, nullable=True)  # Path to sample image
    image_features = Column(Text, nullable=True)  # Serialized feature vector for similarity matching
    
    def __repr__(self):
        return f"<Herb(id={self.id}, common_name='{self.common_name}', scientific_name='{self.scientific_name}')>"


# Create tables
def init_db():
    Base.metadata.create_all(bind=engine)


# Get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

