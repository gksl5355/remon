import enum

class ProductCategoryEnum(str, enum.Enum):
    COMBUSTIBLE = "combustible"
    HTP = "htp"
    E_CIGARETTE = "e_cigarette"

class RiskLevelEnum(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class ChangeTypeEnum(str, enum.Enum):
    NONE = "none"
    APPEND = "append"
    NEW = "new"
    REPEAL = "repeal"
