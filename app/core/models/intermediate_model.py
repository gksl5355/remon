from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from app.core.database import Base

class IntermediateOutput(Base):
    __tablename__ = "intermediate_output"

    intermediate_id = Column(Integer, primary_key=True, index=True) # SERIAL
    intermediate_data = Column(JSONB)
    regulation_id = Column(Integer, ForeignKey("regulations.regulation_id"))

    # Relationships
    regulation = relationship("Regulation", back_populates="intermediate_outputs")