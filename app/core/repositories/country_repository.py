from app.core.models import Country
from .base_repository import BaseRepository

class CountryRepository(BaseRepository[Country]):
    def __init__(self):
        super().__init__(Country)
