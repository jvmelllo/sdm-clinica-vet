"""Validação e normalização de entrada (backend). O frontend repete as regras
básicas para dar resposta imediata, mas a palavra final é sempre desta camada."""
import re
from datetime import date, datetime

from .errors import ApiError, validacao

UFS = {"AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR",
       "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"}
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def so_digitos(texto):
    return re.sub(r"\D", "", str(texto or ""))


def cpf_valido(cpf):
    """Valida CPF pelos dígitos verificadores (aceita com ou sem máscara)."""
    n = so_digitos(cpf)
    if len(n) != 11 or n == n[0] * 11:
        return False
    for tamanho in (9, 10):
        soma = sum(int(d) * p for d, p in zip(n[:tamanho], range(tamanho + 1, 1, -1)))
        digito = (soma * 10) % 11 % 10
        if digito != int(n[tamanho]):
            return False
    return True


def validar_senha(senha):
    """Política mínima: 8+ caracteres, com ao menos uma letra e um número."""
    if not isinstance(senha, str) or len(senha) < 8:
        return "A senha deve ter pelo menos 8 caracteres."
    if not re.search(r"[A-Za-z]", senha) or not re.search(r"\d", senha):
        return "A senha deve conter letras e números."
    return None


def parse_data(texto):
    return datetime.strptime(str(texto).strip(), "%Y-%m-%d").date()


def parse_datahora(texto):
    t = str(texto).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(t, fmt)
        except ValueError:
            continue
    raise ValueError("data/hora inválida")


class Campos:
    """Acumula erros por campo e levanta um único 422 ao final (`ok()`).

    Uso:  c = Campos(json); nome = c.texto("nome", max_len=80); ...; c.ok(); c.v -> dict limpo
    """

    def __init__(self, dados):
        if not isinstance(dados, dict):
            raise ApiError(400, "JSON_INVALIDO", "O corpo da requisição deve ser um objeto JSON.")
        self.d = dados
        self.erros = {}
        self.v = {}

    def _bruto(self, nome, obrigatorio):
        valor = self.d.get(nome)
        if valor is None or (isinstance(valor, str) and valor.strip() == ""):
            if obrigatorio:
                self.erros[nome] = "Campo obrigatório."
            self.v[nome] = None
            return None
        return valor

    def _erro(self, nome, msg):
        self.erros[nome] = msg
        self.v[nome] = None
        return None

    def texto(self, nome, obrigatorio=True, max_len=255, min_len=1):
        b = self._bruto(nome, obrigatorio)
        if b is None:
            return None
        s = str(b).strip()
        if len(s) < min_len or len(s) > max_len:
            return self._erro(nome, f"Deve ter entre {min_len} e {max_len} caracteres.")
        self.v[nome] = s
        return s

    def inteiro(self, nome, obrigatorio=True, minimo=None, maximo=None):
        b = self._bruto(nome, obrigatorio)
        if b is None:
            return None
        try:
            if isinstance(b, bool) or (isinstance(b, float) and not b.is_integer()):
                raise ValueError
            n = int(b)
        except (TypeError, ValueError):
            return self._erro(nome, "Deve ser um número inteiro.")
        if (minimo is not None and n < minimo) or (maximo is not None and n > maximo):
            return self._erro(nome, f"Deve estar entre {minimo} e {maximo}.")
        self.v[nome] = n
        return n

    def decimal(self, nome, obrigatorio=True, minimo=None, maximo=None, casas=2):
        b = self._bruto(nome, obrigatorio)
        if b is None:
            return None
        try:
            if isinstance(b, bool):
                raise ValueError
            n = round(float(str(b).replace(",", ".")), casas)
        except (TypeError, ValueError):
            return self._erro(nome, "Deve ser um número.")
        if (minimo is not None and n < minimo) or (maximo is not None and n > maximo):
            return self._erro(nome, f"Deve estar entre {minimo} e {maximo}.")
        self.v[nome] = n
        return n

    def data(self, nome, obrigatorio=True, futura=True):
        b = self._bruto(nome, obrigatorio)
        if b is None:
            return None
        try:
            d = parse_data(b)
        except ValueError:
            return self._erro(nome, "Use o formato AAAA-MM-DD.")
        if d.year < 1900:
            return self._erro(nome, "Data inválida.")
        if not futura and d > date.today():
            return self._erro(nome, "A data não pode estar no futuro.")
        self.v[nome] = d.strftime("%Y-%m-%d")
        return self.v[nome]

    def datahora(self, nome, obrigatorio=True):
        b = self._bruto(nome, obrigatorio)
        if b is None:
            return None
        try:
            dt = parse_datahora(b)
        except ValueError:
            return self._erro(nome, "Use o formato AAAA-MM-DD HH:MM[:SS].")
        self.v[nome] = dt.strftime("%Y-%m-%d %H:%M:%S")
        return self.v[nome]

    def opcao(self, nome, opcoes, obrigatorio=True, padrao=None):
        b = self._bruto(nome, obrigatorio and padrao is None)
        if b is None:
            self.v[nome] = padrao
            return padrao
        s = str(b).strip().upper()
        if s not in opcoes:
            return self._erro(nome, "Valor inválido. Use: " + ", ".join(sorted(opcoes)) + ".")
        self.v[nome] = s
        return s

    def booleano(self, nome, padrao=None):
        b = self.d.get(nome)
        if b is None:
            self.v[nome] = padrao
            return padrao
        if isinstance(b, bool):
            self.v[nome] = b
        elif str(b).lower() in ("1", "true", "sim"):
            self.v[nome] = True
        elif str(b).lower() in ("0", "false", "nao", "não"):
            self.v[nome] = False
        else:
            return self._erro(nome, "Deve ser verdadeiro ou falso.")
        return self.v[nome]

    def cpf(self, nome="cpf", obrigatorio=True):
        b = self._bruto(nome, obrigatorio)
        if b is None:
            return None
        if not cpf_valido(b):
            return self._erro(nome, "CPF inválido.")
        self.v[nome] = so_digitos(b)
        return self.v[nome]

    def email(self, nome="email", obrigatorio=True):
        b = self._bruto(nome, obrigatorio)
        if b is None:
            return None
        s = str(b).strip().lower()
        if len(s) > 150 or not _EMAIL.match(s):
            return self._erro(nome, "E-mail inválido.")
        self.v[nome] = s
        return s

    def telefone(self, nome="telefone", obrigatorio=True):
        b = self._bruto(nome, obrigatorio)
        if b is None:
            return None
        n = so_digitos(b)
        if len(n) not in (10, 11):
            return self._erro(nome, "Telefone deve ter 10 ou 11 dígitos (com DDD).")
        self.v[nome] = n
        return n

    def cep(self, nome="cep", obrigatorio=True):
        b = self._bruto(nome, obrigatorio)
        if b is None:
            return None
        n = so_digitos(b)
        if len(n) != 8:
            return self._erro(nome, "CEP deve ter 8 dígitos.")
        self.v[nome] = n
        return n

    def uf(self, nome="uf", obrigatorio=True):
        b = self._bruto(nome, obrigatorio)
        if b is None:
            return None
        s = str(b).strip().upper()
        if s not in UFS:
            return self._erro(nome, "UF inválida.")
        self.v[nome] = s
        return s

    def microchip(self, nome="codigo"):
        b = self._bruto(nome, True)
        if b is None:
            return None
        n = so_digitos(b)
        if len(n) != 15 or n != str(b).strip().replace(" ", ""):
            return self._erro(nome, "O microchip RFID deve ter exatamente 15 dígitos numéricos (ISO 11784/11785).")
        self.v[nome] = n
        return n

    def erro(self, nome, msg):
        self.erros[nome] = msg

    def ok(self):
        if self.erros:
            raise validacao(self.erros)
        return self.v


def sanitiza_cep_param(cep):
    n = so_digitos(cep)
    if len(n) != 8:
        raise validacao({"cep": "CEP deve ter 8 dígitos."}, "CEP inválido.")
    return n
