import enum

class ProductCategoryEnum(str, enum.Enum):
    C = "C"  # Combustible
    H = "H"  # HTP
    E = "E"  # E-cigarette

class RiskLevelEnum(str, enum.Enum):
    L = "L"  # Low
    M = "M"  # Medium
    H = "H"  # High

class ChangeTypeEnum(str, enum.Enum):
    NO = "NO" # None
    A = "A"   # Append
    NE = "NE" # New
    R = "R"   # Repeal

class TranslationStatusEnum(str, enum.Enum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"
