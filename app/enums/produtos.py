from enum import Enum

class ProdutoEnum(str, Enum):
    SOJA = "SOJA"
    MILHO = "MILHO"
    TRIGO = "TRIGO"
    ARROZ = "ARROZ"
    ALGODAO = "ALGODAO"
    SORGO = "SORGO"

class UnidadeMedidaEnum(str, Enum):
    SACAS = "SACAS"
    TONELADAS = "TONELADAS"
    KG = "KG"

class TipoFreteEnum(str, Enum):
    A_COMBINAR = "A_COMBINAR"
    FOB_FAZENDA = "FOB_FAZENDA"
    CIF = "CIF"
    POSTO_INDUSTRIA = "POSTO_INDUSTRIA"