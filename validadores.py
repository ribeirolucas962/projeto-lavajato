"""
Validadores e máscaras de campos — Sistema Lava-Jato.
Autor: RINEAL Analytics

Módulo SEM banco de dados: só recebe texto e devolve texto/booleano. Por isso é
fácil de testar (rode `python validadores.py`) e pode ser usado tanto pela
interface (app.py) quanto pelo backend (cadastro_cliente.py).

Duas famílias de funções:

  mascara_*  -> FORMATA enquanto o usuário digita ("47999990000" -> "(47) 99999-0000").
                Nunca reclama de nada: só arruma o que já foi digitado.
  validar_*  -> DIZ SE ESTÁ CERTO (True/False). O CPF/CNPJ é conferido pelo
                dígito verificador, então "111.111.111-11" é rejeitado mesmo
                tendo 11 números.

Regra geral: guardamos no banco o texto JÁ FORMATADO (com pontos e traços), que é
como o cliente lê. Para comparar/validar, a gente tira a formatação com so_digitos().
"""

import re
from datetime import date, datetime


# ================================================================
# Utilitários
# ================================================================
def so_digitos(texto):
    """Devolve apenas os números de um texto: '(47) 9 9999-0000' -> '47999990000'."""
    return re.sub(r"\D", "", texto or "")


# ================================================================
# Máscaras (formatação progressiva, para usar no on_change dos campos)
# ================================================================
def mascara_cpf_cnpj(texto):
    """
    Formata CPF (11 dígitos) ou CNPJ (14 dígitos) conforme o usuário digita.
    Decide sozinho qual é: até 11 números vira CPF, acima disso vira CNPJ.
        '12345678901'    -> '123.456.789-01'
        '12345678000199' -> '12.345.678/0001-99'
    """
    d = so_digitos(texto)[:14]   # ignora o que passar do tamanho de um CNPJ

    if len(d) <= 11:  # CPF: 000.000.000-00
        partes = [d[:3], d[3:6], d[6:9], d[9:11]]
        r = partes[0]
        if partes[1]:
            r += "." + partes[1]
        if partes[2]:
            r += "." + partes[2]
        if partes[3]:
            r += "-" + partes[3]
        return r

    # CNPJ: 00.000.000/0000-00
    partes = [d[:2], d[2:5], d[5:8], d[8:12], d[12:14]]
    r = partes[0]
    if partes[1]:
        r += "." + partes[1]
    if partes[2]:
        r += "." + partes[2]
    if partes[3]:
        r += "/" + partes[3]
    if partes[4]:
        r += "-" + partes[4]
    return r


def mascara_telefone(texto):
    """
    Formata telefone brasileiro com DDD, celular (9 dígitos) ou fixo (8).
        '47999990000' -> '(47) 99999-0000'
        '4733334444'  -> '(47) 3333-4444'
    """
    d = so_digitos(texto)[:11]
    if not d:
        return ""
    if len(d) <= 2:
        return f"({d}"
    ddd, resto = d[:2], d[2:]
    if len(resto) <= 4:
        return f"({ddd}) {resto}"
    corte = 5 if len(resto) > 8 else 4   # celular quebra em 5+4; fixo em 4+4
    return f"({ddd}) {resto[:corte]}-{resto[corte:]}"


def mascara_data(texto):
    """Formata data enquanto digita: '25121990' -> '25/12/1990'."""
    d = so_digitos(texto)[:8]
    if len(d) <= 2:
        return d
    if len(d) <= 4:
        return f"{d[:2]}/{d[2:]}"
    return f"{d[:2]}/{d[2:4]}/{d[4:]}"


def mascara_hora(texto):
    """Formata hora enquanto digita: '0930' -> '09:30'. Usada nos agendamentos."""
    d = so_digitos(texto)[:4]
    if len(d) <= 2:
        return d
    return f"{d[:2]}:{d[2:]}"


def mascara_placa(texto):
    """
    Arruma a placa enquanto o usuário digita: deixa só letras/números, sobe pra
    maiúsculo e limita a 7 caracteres.
        'abc1234'  -> 'ABC-1234'   (padrão antigo: 3 letras + 4 números -> ganha traço)
        'abc1d23'  -> 'ABC1D23'    (padrão Mercosul: sem traço)
    Enquanto ainda não dá pra saber o formato (poucos caracteres), só devolve
    o texto limpo e em maiúsculo, sem inventar traço.
    """
    s = re.sub(r"[^A-Za-z0-9]", "", texto or "").upper()[:7]
    # Formato antigo: depois das 3 primeiras posições vem SÓ número -> ABC-1234.
    if len(s) > 3 and s[3:].isdigit():
        return s[:3] + "-" + s[3:]
    return s   # Mercosul (ABC1D23) ou digitação ainda incompleta


# ================================================================
# Datas (texto brasileiro <-> date do Python)
# ================================================================
def parse_data_br(texto):
    """
    Converte 'dd/mm/aaaa' em um date do Python. Devolve None se o texto estiver
    vazio (campo opcional) ou não for uma data válida (ex.: 31/02/2020).
    """
    t = (texto or "").strip()
    if not t:
        return None
    try:
        return datetime.strptime(t, "%d/%m/%Y").date()
    except ValueError:
        return None


def data_br(d):
    """Formata um date como 'dd/mm/aaaa'. Tolerante a None (devolve '')."""
    try:
        return d.strftime("%d/%m/%Y")
    except Exception:
        return ""


def idade(nascimento):
    """Idade em anos a partir da data de nascimento (None se não houver data)."""
    if not nascimento:
        return None
    hoje = date.today()
    # Subtrai 1 se o aniversário deste ano ainda não chegou.
    return hoje.year - nascimento.year - (
        (hoje.month, hoje.day) < (nascimento.month, nascimento.day)
    )


# ================================================================
# Validações
# ================================================================
def _digito_verificador(numeros, pesos):
    """
    Calcula UM dígito verificador (a conta é a mesma para CPF e CNPJ, muda só o peso):
    soma cada número multiplicado pelo seu peso, tira o resto da divisão por 11 e
    inverte. Resto 0 ou 1 -> dígito 0.
    """
    soma = sum(n * p for n, p in zip(numeros, pesos))
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def validar_cpf(cpf):
    """True se o CPF for válido (11 dígitos + os 2 dígitos verificadores corretos)."""
    d = so_digitos(cpf)
    if len(d) != 11 or d == d[0] * 11:   # '111.111.111-11' e afins são inválidos
        return False
    nums = [int(x) for x in d]
    dv1 = _digito_verificador(nums[:9], range(10, 1, -1))     # pesos 10..2
    dv2 = _digito_verificador(nums[:10], range(11, 1, -1))    # pesos 11..2
    return nums[9] == dv1 and nums[10] == dv2


def validar_cnpj(cnpj):
    """True se o CNPJ for válido (14 dígitos + dígitos verificadores corretos)."""
    d = so_digitos(cnpj)
    if len(d) != 14 or d == d[0] * 14:
        return False
    nums = [int(x) for x in d]
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6] + pesos1
    dv1 = _digito_verificador(nums[:12], pesos1)
    dv2 = _digito_verificador(nums[:13], pesos2)
    return nums[12] == dv1 and nums[13] == dv2


def validar_cpf_cnpj(documento):
    """
    True se o documento for um CPF **ou** um CNPJ válido.
    Campo vazio é considerado VÁLIDO (o CPF é opcional no cadastro) — quem exige
    preenchimento é a tela, não o validador.
    """
    d = so_digitos(documento)
    if not d:
        return True
    if len(d) == 11:
        return validar_cpf(d)
    if len(d) == 14:
        return validar_cnpj(d)
    return False   # 8 dígitos, 13 dígitos... não é nem um nem outro


def validar_email(email):
    """
    True se o e-mail tiver a cara de um e-mail (algo@algo.algo).
    Vazio é válido (campo opcional). Não é uma validação rigorosa de RFC — é a
    checagem prática que pega erro de digitação ('joao@gmail' sem o .com).
    """
    e = (email or "").strip()
    if not e:
        return True
    return re.match(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$", e) is not None


def validar_telefone(telefone):
    """
    True se o telefone tiver 10 (fixo com DDD) ou 11 (celular com DDD) dígitos.
    Vazio é válido (campo opcional), mas sem telefone não há WhatsApp.
    """
    d = so_digitos(telefone)
    if not d:
        return True
    return len(d) in (10, 11)


def validar_placa(placa):
    """
    True se a placa for do padrão antigo (ABC-1234) ou Mercosul (ABC1D23).
    O traço e espaços são ignorados na conferência — 'ABC-1234' e 'ABC1234'
    valem igual. Vazio é considerado VÁLIDO (quem exige a placa é a tela).

        antigo   : 3 letras + 4 números          -> ABC1234
        Mercosul : 3 letras + número + letra + 2 números -> ABC1D23
    """
    s = re.sub(r"[^A-Za-z0-9]", "", placa or "").upper()
    if not s:
        return True
    antigo = re.match(r"^[A-Z]{3}[0-9]{4}$", s)
    mercosul = re.match(r"^[A-Z]{3}[0-9][A-Z][0-9]{2}$", s)
    return bool(antigo or mercosul)


def validar_ano_veiculo(ano):
    """
    True se o ano do veículo estiver numa faixa razoável: de 1900 até o ano que
    vem (concessionária vende o modelo do próximo ano). Assim '1800' e '3050'
    são barrados. Vazio é válido (campo opcional).
    """
    if ano in (None, ""):
        return True
    try:
        a = int(ano)
    except (TypeError, ValueError):
        return False
    return 1900 <= a <= date.today().year + 1


# ================================================================
# TESTE RÁPIDO (python validadores.py)
# ================================================================
if __name__ == "__main__":
    print("— Máscaras —")
    print(" CPF   :", mascara_cpf_cnpj("52998224725"))
    print(" CNPJ  :", mascara_cpf_cnpj("11222333000181"))
    print(" Celular:", mascara_telefone("47999990000"))
    print(" Fixo  :", mascara_telefone("4733334444"))
    print(" Data  :", mascara_data("25121990"))
    print(" Hora  :", mascara_hora("0930"))
    print(" Placa antiga :", mascara_placa("abc1234"))
    print(" Placa Mercosul:", mascara_placa("abc1d23"))

    print("\n— Validações (esperado: True, False, True, False) —")
    print(" CPF válido   :", validar_cpf("529.982.247-25"))
    print(" CPF repetido :", validar_cpf("111.111.111-11"))
    print(" CNPJ válido  :", validar_cnpj("11.222.333/0001-81"))
    print(" CNPJ errado  :", validar_cnpj("11.222.333/0001-99"))

    print("\n— E-mail (esperado: True, False) —")
    print(" ok    :", validar_email("joao@gmail.com"))
    print(" errado:", validar_email("joao@gmail"))

    print("\n— Placa (esperado: True, True, False) —")
    print(" antiga  :", validar_placa("ABC-1234"))
    print(" Mercosul:", validar_placa("ABC1D23"))
    print(" errada  :", validar_placa("AB12"))

    print("\n— Ano do veículo (esperado: True, False, False) —")
    print(" 2015:", validar_ano_veiculo(2015))
    print(" 1800:", validar_ano_veiculo(1800))
    print(" 3050:", validar_ano_veiculo(3050))

    nasc = parse_data_br("25/12/1990")
    print("\n— Data —")
    print(" 25/12/1990 ->", nasc, "| idade:", idade(nasc))
    print(" 31/02/2020 ->", parse_data_br("31/02/2020"), "(inválida, vira None)")
