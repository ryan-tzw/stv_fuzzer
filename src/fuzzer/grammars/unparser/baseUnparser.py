from ..astBuilder.astNode import AstNode
from abc import ABC, abstractmethod


class Unparser(ABC):
    """Base class for AST -> string conversion."""

    @abstractmethod
    def unparse(self, node: AstNode) -> str:
        raise NotImplementedError
