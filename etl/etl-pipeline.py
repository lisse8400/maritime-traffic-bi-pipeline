
import os
import sys
import mysql.connector as mysql
import pyodbc
from datetime import datetime
import random
import csv

# Variaveis de ligação aos SGBD
# MySQL
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1") # ip da maquina onde está o mysql (localhost)
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306")) #porta do mysql (só mudar se alterou na instalação)
MYSQL_USER = os.getenv("MYSQL_USER", "root") # introduzir user
MYSQL_PWD  = os.getenv("MYSQL_PWD",  "") # introduzir password
MYSQL_DB   = os.getenv("MYSQL_DB",   "TP_G2") # introduzir nome da bd operacional

# SQL Server
MSSQL_HOST   = os.getenv("MSSQL_HOST", "127.0.0.1") # ip da maquina onde está o mysql (localhost)
MSSQL_PORT   = int(os.getenv("MSSQL_PORT", "1433")) #porta do mssql (só mudar se alterou na instalação)
MSSQL_USER   = os.getenv("MSSQL_USER", "sa") # introduzir user
MSSQL_PWD    = os.getenv("MSSQL_PWD",  "")  # introduzir password
MSSQL_DB     = os.getenv("MSSQL_DB",   "TP") # introduzir nome da bd dw
MSSQL_DRIVER = os.getenv("MSSQL_DRIVER", "ODBC Driver 18 for SQL Server")  # o driver que foi instalado

#Nome do ficheiro CSV
CSV_PATH = os.getenv("CSV_VIAGENS_PATH", r"C:\Users\leono\Downloads\dados_atualizado.csv")

CSV_CURRENCY = "USD"   
DW_CURRENCY  = "EUR"
EXCHANGE_RATE = 0.86


# ligação ao SGBD mysql

def get_mysql_conn():
    """Liga ao MySQL via mysql-connector-python."""
    return mysql.connect(
        host=MYSQL_HOST, port=MYSQL_PORT,
        user=MYSQL_USER, password=MYSQL_PWD,
        database=MYSQL_DB, autocommit=True, charset="utf8mb4"
    )

# ligação ao SGBD MSSQL
def get_mssql_conn():
    """Liga ao SQL Server via pyodbc (schema padrão: dbo)."""
    conn_str = (
        f"DRIVER={{{MSSQL_DRIVER}}};SERVER={MSSQL_HOST},{MSSQL_PORT};"
        f"DATABASE={MSSQL_DB};UID={MSSQL_USER};PWD={MSSQL_PWD};"
        f"TrustServerCertificate=Yes;"
    )
    return pyodbc.connect(conn_str)

# --------------------------------------------
# Funções ETL Converte o formato da data e o tipo de moeda
# --------------------------------------------
def parse_data(dstr):
    """Converte 'dd/mm/yyyy' para datetime.date."""
    if not dstr:
        return None
    return datetime.strptime(dstr, "%d/%m/%Y").date()

def parse_taxa_e_converter(taxa_str):
    """
    Converte string '9988,3' da moeda do CSV para a moeda do DW.
    """
    if taxa_str is None:
        return 0.0
    s = str(taxa_str).strip()
    if s == "":
        return 0.0
    # tratar vírgula decimal e possíveis pontos de milhar
    s = s.replace(".", "").replace(",", ".")
    valor_origem = float(s)
    valor_dw = valor_origem * EXCHANGE_RATE
    return valor_dw

#Normalização de float e ints provinientes do csv

def to_float_csv(x):
    if x is None:
        return 0.0
    s = str(x).strip()
    if s == "":
        return 0.0
    # 1) remove pontos de milhar
    # 2) troca vírgula por ponto
    s = s.replace(".", "").replace(",", ".")
    return float(s)

def to_int_csv(x):
    if x is None:
        return 0
    s = str(x).strip()
    if s == "":
        return 0
    # remove milhar
    s = s.replace(".", "")
    return int(s)



def gerar_tamanho_barco_por_capacidade(capacidade_teu):
    """
    Gera um tamanho (comprimento em metros) credível
    apenas com base na capacidade TEU.
    """
    cap = capacidade_teu or 0

    if cap <= 2000:
        minimo, maximo = 120.0, 200.0    # navios pequenos
    elif cap <= 8000:
        minimo, maximo = 200.0, 300.0    # navios médios
    else:
        minimo, maximo = 300.0, 400.0    # navios grandes

    # mesma capacidade → mesmo tamanho em todas as execuções
    random.seed(cap)
    return round(random.uniform(minimo, maximo), 2)


# --------------- FUNÇÕES AUXILIARES DIMENSÕES ---------------

# Todas as funções utilizam  1) SELECT pelos atributos se não existir, 2) INSERT e por fim  3) SELECT outra vez para obter o Id

def get_or_create_data_chegada(cur, data_chegada):
    
    dia = data_chegada.day # retira o dia
    mes = data_chegada.month  # retira o mes
    ano = data_chegada.year # retira ano
    
    # 1) Tenta encontrar pela data, se existir optiomo, devolve logo a data
    cur.execute("""SELECT id_data_chegada 
        FROM data_chegada 
        WHERE dia = ? AND mes = ? AND ano = ?;""", (dia, mes, ano))
    row = cur.fetchone()
    if row:
        return row[0]


 

    # 3) Operação etl, para calcular o trimestre e o semestre
    trimestre = (mes - 1) // 3 + 1
    semestre = 1 if mes <= 6 else 2
    #insere os valores na tabela dimensão data_chegada.
    # 2) Se não existe, insere uma nova data
    cur.execute("""
        INSERT INTO data_chegada (dia, mes, ano,trimestre, semestre)
        VALUES (?, ?, ?, ?, ?);
    """, (dia, mes, ano, trimestre, semestre))

    # 3) Re-lê 
    cur.execute("""
        SELECT id_data_chegada 
        FROM data_chegada 
        WHERE dia = ? AND mes = ? AND ano = ?;
    """, (dia, mes, ano))
    row = cur.fetchone()
    if not row:
        raise RuntimeError("Falha ao obter IdTempo após INSERT em DimTempo.")
    return row[0]


def get_or_create_condutor(cur, condutor):
    nome  = condutor["nomecondutor"]
    idade = condutor["idadecondutor"]
    cert  = condutor["certificacao"]

    # 1) procura pelos atributos
    cur.execute("SELECT id_condutor FROM condutor WHERE nome = ? AND idade = ? AND certificacao = ?;", (nome, idade, cert))
    row = cur.fetchone()
    if row:
        return row[0]

    # 2) insere
    cur.execute("""
        INSERT INTO condutor
            ( nome, idade, certificacao)
        VALUES (?, ?, ?);
    """, (nome, idade, cert))

    # 3) re-lê
    cur.execute("SELECT id_condutor FROM condutor WHERE nome = ? AND idade = ? AND certificacao = ?;", (nome, idade, cert))
    row = cur.fetchone()
    if not row:
        raise RuntimeError("Falha ao obter id_condutor após INSERT em condutor.")
    return row[0]


def get_or_create_barco(cur, barco):
    nome  = barco["nomebarco"]
    tipo  = barco["tipobarco"]
    cap   = barco["capacidadeteu"]
    tam   = barco["tamanhobarco"]

    # 1) procura pelos atributos
    cur.execute("""
        SELECT id_barco
        FROM barco
        WHERE nome = ? AND tipo = ? AND capacidade = ? AND tamanho=?;
    """, (nome, tipo, cap, tam))
    row = cur.fetchone()
    if row:
        return row[0]

    # 2) insere
    cur.execute("""
        INSERT INTO barco
            ( nome, tipo, capacidade, tamanho)
        VALUES (?, ?, ?,?);
    """, (nome, tipo, cap , tam))

    # 3) re-lê
    cur.execute("""
        SELECT id_barco
        FROM barco
        WHERE nome = ? AND tipo = ? AND capacidade = ? AND tamanho=?;
    """, (nome, tipo, cap,tam))
    row = cur.fetchone()
    if not row:
        raise RuntimeError("Falha ao obter id_barco após INSERT em barco.")
    return row[0]



def get_or_create_origem(cur, origem):
    # Ler valores vindos do MySQL
    pais   = origem.get("pais_origem")
    cidade = origem.get("cidade_origem")

    # 1) Tratamento ETL: NULLs e espaços
    if pais is None or str(pais).strip() == "":
        pais = "DESCONHECIDO"
    else:
        pais = str(pais).strip()

    if cidade is None or str(cidade).strip() == "":
        cidade = "DESCONHECIDA"
    else:
        cidade = str(cidade).strip()

    # 2) Ver se já existe essa origem
    cur.execute(
        "SELECT id_origem FROM origem WHERE pais = ? AND cidade = ?;",
        (pais, cidade)
    )
    row = cur.fetchone()
    if row:
        return row[0]

    # 3) Não existe -> inserir e obter o id diretamente do INSERT
    cur.execute("""
        INSERT INTO origem (pais, cidade)
        OUTPUT INSERTED.id_origem
        VALUES (?, ?);
    """, (pais, cidade))

    row = cur.fetchone()
    if not row:
        raise RuntimeError(
            f"Falha ao obter id_origem após INSERT em origem. "
            f"pais={pais!r}, cidade={cidade!r}"
        )

    return row[0]

def etl_mysql_para_dw():
    print("1 - Ligação ao MySQL")
    mysql_conn  = get_mysql_conn() # ligação ao mysql
    print("2 - Ligação ao MsSQL")
    sqlsrv_conn = get_mssql_conn() 

    try:
        mysql_cur = mysql_conn.cursor(dictionary=True)
        sqlsrv_cur = sqlsrv_conn.cursor()

        # 1) Ler os consumos com joins para ter tudo numa só linha, de forma a ser mais simples
        mysql_cur.execute("""
            SELECT
                v.idviagem,
                v.datapartida,
                v.datachegada,
                v.tipoviagem,


                c.idcondutor,
                c.nomecondutor,
                c.idadecondutor,
                c.certificacao,


                b.idbarco,
                b.nomebarco,
                b.tipobarco,
                b.capacidadeteu,
                b.tamanhobarco,

                lo.pais   AS pais_origem,
                lo.cidade AS cidade_origem,
              
              
              
              COALESCE(SUM(DISTINCT t.valor), 0)        AS valor_taxas,
              COALESCE(SUM(ct.pesocontentor), 0)         AS peso_total_contentores,
              COALESCE(COUNT(ct.idcontentor), 0)        AS num_contentores


            FROM viagem v
            JOIN condutor    c  ON v.condutor_idcondutor        = c.idcondutor
            JOIN barco       b  ON v.barco_idbarco              = b.idbarco
            JOIN localizacao lo ON v.localizacao_idlocalizacao  = lo.idlocalizacao
            LEFT JOIN taxas t    ON t.viagem_idviagem           = v.idviagem
            LEFT JOIN contentores ct ON ct.viagem_idviagem      = v.idviagem
                
            WHERE v.datachegada IS NOT NULL
            
            
             GROUP BY
                v.idviagem,
                v.datapartida,
                v.datachegada,
                v.tipoviagem,
                c.idcondutor,
                c.nomecondutor,
                c.idadecondutor,
                c.certificacao,
                b.idbarco,
                b.nomebarco,
                b.tipobarco,
                b.capacidadeteu,
                b.tamanhobarco,
                lo.pais,
                lo.cidade
            ORDER BY v.idviagem;
        """)

        rows = mysql_cur.fetchall()
        print(f"Registos lidos do MySQL: {len(rows)}")

        for idx, r in enumerate(rows, start=1):
            data_chegada = r["datachegada"]
           
            # 1)dat_chegada
            id_data = get_or_create_data_chegada(sqlsrv_cur, data_chegada)

            # 2) Condutor
            condutor = {
                "nomecondutor":  r["nomecondutor"],
                "idadecondutor": r["idadecondutor"],
                "certificacao":  r["certificacao"],
            }
            id_condutor = get_or_create_condutor(sqlsrv_cur, condutor)

            # 3) Barco
            barco = {
                "nomebarco":     r["nomebarco"],
                "tipobarco":     r["tipobarco"],
                "capacidadeteu": r["capacidadeteu"],
                "tamanhobarco": r["tamanhobarco"],
            }
            id_barco = get_or_create_barco(sqlsrv_cur, barco)

            # 4) origem
            origem = {
                "pais_origem":   r["pais_origem"],
                "cidade_origem": r["cidade_origem"],
            }
            id_origem = get_or_create_origem(sqlsrv_cur, origem)

          

            # 6) Fact table
          
            data_partida = r["datapartida"]
            tipo_viagem = r["tipoviagem"]
            
            valor_taxas = float(r["valor_taxas"])
            peso_total  = float(r["peso_total_contentores"])
            num_cont    = int(r["num_contentores"])

            # INSERT na fact viagem no SQL Server 
            sqlsrv_cur.execute("""
                INSERT INTO viagem
                    (valor_taxas,
                     peso_total_contentores,
                     num_contentores,
                     tipo_viagem,
                     data_partida,
                     origem_id_origem,
                     data_chegada_id_data_chegada,
                     condutor_id_condutor,
                     barco_id_barco)
                VALUES ( ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                valor_taxas,
                peso_total,
                num_cont,
                tipo_viagem,
                data_partida,
                id_origem,
                id_data,
                id_condutor,
                id_barco
            ))

            if idx % 200 == 0:
                print(f"... {idx} viagens inseridas")


        sqlsrv_conn.commit()
        print(f"ETL concluido. Registos processados: {len(rows)}")
    finally:
        mysql_conn.close()
        sqlsrv_conn.close()

 
def etl_csv_para_dw():
    global conn, cursor

    print("1 - Ligação ao SQL Server (DW)")
    conn = get_mssql_conn()
    cursor = conn.cursor()

    try:
        print(f"2 - A abrir ficheiro CSV: {CSV_PATH}")
        with open(CSV_PATH, mode="r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f, delimiter=";")
            linhas = 0

            for row in reader:
                #data e moeda
                data_partida = parse_data(row["datapartida"])
                data_chegada = parse_data(row["datachegada"])
                valor_taxas = parse_taxa_e_converter(row["taxa"]) 
               
                print("3 - Introduzir os valores da Dimensão data_chegada") 
                id_data = get_or_create_data_chegada(cursor, data_chegada)
                
                print("3 - Introduzir os valores da Dimensão condutor") 
                condutor = {
                    "nomecondutor": row["nomecondutor"],
                    "idadecondutor": int(row["idadecondutor"]) if row["idadecondutor"] else None,
                    "certificacao": row["certificacao"],
                }
                id_condutor = get_or_create_condutor(cursor, condutor)
                
                capacidade = int(row["capacidadeteu"]) if row["capacidadeteu"] else 0

                print("4 - Introduzir os valores da Dimensão barco") 
                barco = {
                    "nomebarco": row["nomebarco"],
                    "tipobarco": row["tipobarco"],
                    "capacidadeteu": capacidade,
                    "tamanhobarco": gerar_tamanho_barco_por_capacidade(capacidade),
                }
                id_barco = get_or_create_barco(cursor, barco)   
                
                print("5 - Introduzir os valores da Dimensão origem") 
                origem = {
                    "pais_origem": row["pais_origem"],
                    "cidade_origem": row["cidade_origem"],
                }
                id_origem = get_or_create_origem(cursor, origem)    
                
                
                print("7 - (outro ETL) Calcular o custo total a tabela de factos") 
                peso_total = to_float_csv(row["peso"])
                num_cont = to_int_csv(row["numerocontentares"])
               

              

                tipos_carga = ["mista", "carga", "servico", "outro"]

                if peso_total == 0:
                    tipo_viagem = "passageiros"
                else:
                    tipo_viagem = random.choice(tipos_carga)


                print("8 - Inserir dados na tabela de factos") 
                cursor.execute(
                    """
                    INSERT INTO viagem (
                        valor_taxas,
                        peso_total_contentores,
                        num_contentores,
                        tipo_viagem,
                        data_partida,
                        origem_id_origem,
                        data_chegada_id_data_chegada,
                        condutor_id_condutor,
                        barco_id_barco
                        )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,(
                  valor_taxas,
                  peso_total,
                  num_cont,
                  tipo_viagem,
                  data_partida,
                  id_origem,
                  id_data,
                  id_condutor,
                  id_barco
                )
                )

                linhas += 1
                if linhas % 100 == 0:
                    conn.commit()
                    print(f"{linhas} linhas processadas...")

        conn.commit()
        print(f"ETL concluído com sucesso! Linhas processadas: {linhas}")

    except FileNotFoundError:
        print(f"ERRO: ficheiro CSV não encontrado: {CSV_PATH}")
        print("Verifica o caminho/nome do ficheiro em CSV_PATH no script.")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()



def main():
   

    etl_mysql_para_dw()
    etl_csv_para_dw()
if __name__ == "__main__":
    main()



