import os
import time
import json
import datetime
from decimal import Decimal
from typing import List, Tuple, Dict
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_community.utilities import SQLDatabase
from langchain.prompts import PromptTemplate
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, BaseMessage
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

#print("Sorted: ",result)

#print(json.dumps(result, indent=2, default=list))

#test = db.run_no_throw(updata_inventario.format(cantidad=100, product_name="Huevos"))

def _fetch_inventory_from_db_internal() -> List[Dict]:
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


    result = list(filter(lambda x: x["cantidad"] > 0, result))
    return result

@tool
def get_ingredients() -> str:
    """
    Devuelve la lista de ingredientes disponibles en el inventario.
    """
    inventory_list = _fetch_inventory_from_db_internal()
    # Devuelve el resultado como string, que es lo que suelen manejar mejor las tools
    return json.dumps(inventory_list)

@tool
def update_inventory(productos:List[Tuple[int,int]]) -> str:
    """
    Actualiza el inventario restando la cantidad de un producto.
    recibe el id_producto y la cantidad a restar.
    si el id_producto de huevos es 1 y se usanron 2 unidades, se debe llamar a la función así:
    update_inventory([1, 2])
    si se quiere actualizar varios productos, se puede llamar así:
    update_inventory([(1, 2), (2, 3)])
    siempre con valores positivos.
    """
    updata_inventario = """
        UPDATE inventario
        SET cantidad = {cantidad}
        WHERE id_producto = {id_producto};
    """
    try:
        for id_producto, cantidad in productos:
            db.run_no_throw(updata_inventario.format(cantidad=cantidad, id_producto=id_producto))
            print("cantidad: ", cantidad)
            print("id_producto: ", id_producto)
        return f"Inventario actualizado: {cantidad} {id_producto} restados."
    except Exception as e:
        return f"Error al actualizar el inventario: {e}"

# msj = [("system", SYS.format(ingredients=json.dumps(result, indent=2, default=list)))]

prompt = PromptTemplate.from_template(
    template=SYS
)

tools = [get_ingredients, update_inventory]
agent = create_react_agent(llm, tools=tools, prompt=SYS)

def graph():
    try:
        print("Intentando generar gráfico del agente con Mermaid...")

        # Llama al método directamente sobre tu objeto 'agent'
        # (LangGraph a menudo permite esto en los objetos compilados)
        png_bytes = agent.get_graph().draw_mermaid_png() # <--- Llamada sobre tu 'agent'

        # Guarda los bytes en un archivo PNG
        with open("mi_agente_graph.png", "wb") as f:
            f.write(png_bytes)
        print("¡Gráfico del agente guardado como mi_agente_graph.png!")

    except AttributeError:
        print("Error: Parece que el objeto 'agent' devuelto por create_react_agent")
        print("no tiene directamente el método 'draw_mermaid_png'.")
        print("Podrías necesitar construir el grafo manualmente con StateGraph para visualizarlo así,")
        print("o buscar si expone un método como 'get_graph()' y llamar .draw_mermaid_png() sobre eso.")
    except ImportError:
        print("Error: Faltan dependencias para generar el gráfico con Mermaid.")
        print("Intenta instalar playwright: pip install playwright && playwright install")
    except Exception as e:
        print(f"Error inesperado al generar o guardar el gráfico: {e}")

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
