from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Float, Boolean, Date, JSON

Base = declarative_base()


class Product(Base):
    __tablename__ = "product"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    category = Column(String)
    nicotine = Column(Float)
    tar = Column(Float)
    menthol = Column(Boolean)
    flavor = Column(Boolean)
    battery_capacity = Column(Float)
    label_size = Column(Float)
    warning_area = Column(Float)
    certified = Column(Boolean)
    export_country = Column(String)


class Regulation(Base):
    __tablename__ = "regulation"
    id = Column(Integer, primary_key=True)
    country = Column(String)
    category = Column(String)
    content = Column(String)
    nicotine_limit = Column(Float)
    label_size_limit = Column(Float)
    battery_capacity_limit = Column(Float)


class MappingResult(Base):
    __tablename__ = "mapping_result"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer)
    regulation_id = Column(Integer)
    hybrid_score = Column(Float)
    matched_fields = Column(JSON)
    impact_level = Column(Integer)
