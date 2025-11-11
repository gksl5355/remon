from app.core.models import GlossaryTerm
from .base_repository import BaseRepository

class GlossaryTermRepository(BaseRepository[GlossaryTerm]):
    def __init__(self):
        super().__init__(GlossaryTerm)
