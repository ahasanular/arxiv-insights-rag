import re

from sqlalchemy.orm import DeclarativeBase, declared_attr


class Base(DeclarativeBase):
    @declared_attr.directive
    def __tablename__(cls) -> str:
        # Converts CamelCase to snake_case for table names automatically
        return re.sub(r"(?<!^)(?=[A-Z])", "_", cls.__name__).lower()
