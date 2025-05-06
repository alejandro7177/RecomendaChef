import os
import json
import datetime
import pandas as pd
from decimal import Decimal
from typing import List, Literal, Dict
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_community.utilities import SQLDatabase
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import BaseMessage
from langchain.tools import tool
from prompt import SYS

load_dotenv(".env")
MODEL= os.environ.get("GROPQ_MODEL")
API_KEY=os.environ.get("GROQ_API_KEY")

DB_USER=os.environ.get("DB_USER")
DB_PASSWORD=os.environ.get("DB_PASSWORD")
DB_HOST=os.environ.get("DB_HOST") 
DB_PORT=os.environ.get("DB_PORT")
DB_NAME=os.environ.get("DB_NAME")

DATABASE_URI = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

db = SQLDatabase.from_uri(DATABASE_URI)

llm = ChatGroq(
    model=MODEL,
    temperature=0,
    api_key=API_KEY,
    streaming=True,
)

def _fetch_inventory_from_db_internal(type=None) -> List[Dict]:
    """
    Función interna para obtener y parsear el inventario directamente de la DB.
    Devuelve una lista de diccionarios.
    """
    # Usa la variable global 'db'
    result_raw = db.run_no_throw("""
    SELECT
        p.nombre AS nombre_producto,
        p.id_producto AS id_producto,
        i.cantidad,
        p.unidad_medida AS unidad_medida,
        i.fecha_vencimiento
    FROM
        producto p
    JOIN
        inventario i ON p.id_producto = i.id_producto;
    """)

    if not result_raw:
        print("Advertencia: La consulta de inventario no devolvió resultados.")
        return []

    try:
        # Pasar datetime y Decimal al scope de eval
        rows = eval(result_raw, {"Decimal": Decimal, "datetime": datetime})
    except Exception as e:
        print(f"Error crítico evaluando resultado de DB: {e}")
        print(f"Resultado crudo que causó el error: {result_raw}")
        return [] # Devuelve lista vacía en caso de error de parsing

    result = []
    for row in rows:
        try:
            item = {
                "nombre_producto": row[0],
                "id_producto": row[1],
                "cantidad": float(row[2]), # Convertir Decimal a float
                "unidad_medida": row[3],
                "fecha_vencimiento": 
                    row[4].isoformat() if isinstance(row[4], (datetime.date, datetime.datetime)) else None
            }
            result.append(item)
        except IndexError:
            print(f"Advertencia: Fila con formato incorrecto encontrada en resultados de DB: {row}")
        except Exception as e:
            print(f"Error procesando fila {row}: {e}")

    result = list(\
        filter(
            lambda x: x.get("fecha_vencimiento") is None or datetime.datetime.fromisoformat(x.get("fecha_vencimiento")) > datetime.datetime.now(), result
        )
    ) #filtro vencido
    result = list(filter(lambda x: x.get("cantidad") > 0, result)) #filtro cantidad

    return result

@tool
def get_recetas(
    tipo:Literal["vegetariano","vegano","normal","celiaco"] = "normal",
    complejidad: Literal["facil", "normal", "dificil"]= "normal"
    ) -> List:
    """
    Args:
        tipo: Tipo de recetas que se necesita de filtro para traer las recetas relevantes los tipos de recetas son ["vegetariano","vegano","normal","celiaco"] por defecto es normal que incluye todo

        complejidad: Complejidad de receta de la receta puede ser ["facil", "normal", "dificil"] por defecto es normal que incluye

    """
    def calcular_puntos_disponibilidad(row, inventario_ids):
        """
        Calcula cuántos IDs de productos necesarios en la fila
        están presentes en el inventario_ids. Suma 1 punto por cada coincidencia.
        """
        productos_receta = row['productos necesarios']
        puntos_por_disponibilidad = 0

        if not isinstance(productos_receta, list): return 0

        if not productos_receta: return 0

        for producto_dict in productos_receta:
            id_necesario = producto_dict.get('id')
            if id_necesario is not None and id_necesario in inventario_ids:
                puntos_por_disponibilidad += 1

        return puntos_por_disponibilidad

    inventory_list = _fetch_inventory_from_db_internal()

    df = pd.read_json("recetas.json")
    df["score"] = 0

    if tipo == "vegetariano":
        df.loc[df["tipo"]=="vegetariano", 'score'] += 10
        df.loc[df["tipo"]=="vegano", 'score'] += 10

    elif tipo == "vegano":
        df.loc[df["tipo"]=="vegano", 'score'] += 10

    elif tipo=="celiaco":
        df.loc[df["tipo"]=="celiaco", 'score'] += 10

    elif tipo=="normal":
        df.loc[df["tipo"]=="normal", 'score'] += 10
        df.loc[df["tipo"]=="vegetariano", 'score'] += 10
        df.loc[df["tipo"]=="vegano", 'score'] += 10
        df.loc[df["tipo"]=="celiaco", 'score'] += 10
    
    if complejidad=="facil":
        df.loc[df["complejidad"]=="facil", 'score'] += 5

    elif complejidad=="normal":
        df.loc[df["complejidad"]=="normal", 'score'] += 5
        df.loc[df["complejidad"]=="facil", 'score'] += 5

    elif complejidad=="dificil":
        df.loc[df["complejidad"]=="dificil", 'score'] += 7
        df.loc[df["complejidad"]=="normal", 'score'] += 2


    #Se hace un primer puntuado de las recetas 20 recetas
    df = df.sort_values(by="score", ascending=False).head(20)

    puntos_disponibilidad = df.apply(
        calcular_puntos_disponibilidad,
        axis=1, 
        inventario_ids=[i.get("id") for i in inventory_list]
    )
    
    df["score"] = df["score"] + puntos_disponibilidad

    df = df.sort_values(by="score", ascending=False).head(3)

    return json.dumps(df.to_dict("records"), indent=2)

tools = [get_recetas]
agent = create_react_agent(llm, tools=tools, prompt=SYS)


class Orquetador:
    def invoke_agents(self, mjs:List[BaseMessage]) -> str:
        inputs = {"messages": mjs}
        result = agent.invoke(inputs)
        return result["messages"][-1]

    def get_inventory_data(self) -> list:
        result = _fetch_inventory_from_db_internal()
        return result

    def check_product_exists(self, name)->bool:
        """
        Verifica si el producto existe en la base de datos.
        """
        result = db.run_no_throw(f"""
        SELECT EXISTS (
            SELECT 1
            FROM inventario inv
            INNER JOIN producto prod ON inv.id_producto = prod.id_producto
            WHERE prod.nombre = '{name}'
        );
        """)
        print("Exist: ", type(result))
        return result == "[(True,)]"
    
    def update_inventory_quantity(self, name_product, quantity):
        """
        Actualiza la cantidad de un producto en el inventario.
        """
        try:
            result = db.run_no_throw(f"""
            UPDATE inventario
            SET cantidad = cantidad - {quantity}
            WHERE id_producto = (
                SELECT id_producto
                FROM producto
                WHERE nombre = '{name_product}'
            );
            """)
            return True
        except Exception as e:
            print(f"Error al actualizar el inventario: {e}")
            return False
        
if __name__ == "__main__":
    input_data = {"tipo": "vegetariano", "complejidad": "normal"}
    result = get_recetas.invoke(input_data)
    print(result)

