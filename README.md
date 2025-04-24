# RecomendaChef 🍳👨‍🍳

## Descripción
RecomendaChef es un bot de Telegram inteligente que ayuda a los usuarios a gestionar su inventario de alimentos y recomienda recetas basadas en los ingredientes disponibles. Utilizando modelos de IA avanzados, el bot prioriza los ingredientes que están próximos a vencer, ayudando a reducir el desperdicio de alimentos y facilitando la planificación de comidas.

## Características principales ✨

- **Recomendación de recetas**: Sugiere recetas que pueden prepararse con los ingredientes disponibles en el inventario del usuario.
- **Gestión de inventario**: Permite a los usuarios visualizar y actualizar su inventario de alimentos.
- **Priorización de ingredientes**: Da preferencia a los ingredientes con fechas de vencimiento próximas.
- **Interfaz conversacional**: Implementa un sistema de chat natural para interactuar con los usuarios.
- **Sugerencias de compras**: Recomienda ingredientes adicionales cuando faltan pocos elementos para completar una receta.

## Requisitos previos 📋

- Python 3.8+
- PostgreSQL
- Cuenta de Telegram
- Token de API de Telegram (obtenido a través de @BotFather)
- Cuenta en Groq para acceso a modelos de IA

## Instalación 🔧

1. **Clonar el repositorio**:
   ```bash
   git clone https://github.com/tu-usuario/RecomendaChef.git
   cd RecomendaChef
   ```

2. **Crear entorno virtual**:
   ```bash
   python -m venv env
   source env/bin/activate  # En Windows: env\Scripts\activate
   ```

3. **Instalar dependencias**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar variables de entorno**:
   Crea un archivo `.env` con la siguiente estructura:
   ```
   TELEGRAM_BOT_TOKEN=tu_token_de_telegram
   GROQ_API_KEY=tu_api_key_de_groq
   GROPQ_MODEL=nombre_del_modelo_groq

   DB_USER=usuario_postgres
   DB_PASSWORD=contraseña_postgres
   DB_HOST=host_postgres
   DB_PORT=puerto_postgres
   DB_NAME=nombre_base_datos
   ```

5. **Configurar la base de datos**:
   - Crear una base de datos PostgreSQL
   - Asegurarse de que las tablas `producto` e `inventario` estén creadas con los campos necesarios

## Uso 🚀

1. **Iniciar el bot**:
   ```bash
   python main.py
   ```

2. **Comandos disponibles en Telegram**:
   - `/start` - Inicia la conversación con el bot
   - `/inventario` - Muestra los productos disponibles en el inventario
   - `/update_inv` - Actualiza la cantidad de un producto en el inventario
   - También puedes hablar naturalmente con el bot para pedir recomendaciones de recetas

## Estructura del proyecto 📁

- **bot.py**: Implementa la lógica del bot de Telegram y la gestión de comandos.
- **graph.py**: Contiene la implementación del orquestador de agentes con LangGraph y la conexión a la base de datos.
- **main.py**: Punto de entrada de la aplicación que inicializa el bot y el orquestador.
- **prompt.py**: Define el prompt del sistema para el modelo de IA.

## Flujo de funcionamiento 🔄

1. El usuario interactúa con el bot a través de Telegram.
2. El bot procesa las solicitudes utilizando el orquestador de agentes basado en LangGraph.
3. Para recomendar recetas, el sistema consulta la base de datos para obtener los ingredientes disponibles.
4. El modelo de IA genera recomendaciones priorizando los ingredientes próximos a vencer.
5. El bot envía las sugerencias al usuario a través de Telegram.

## Contribuir 🤝

Las contribuciones son bienvenidas. Para contribuir:

1. Haz un fork del repositorio
2. Crea una rama para tu característica (`git checkout -b feature/nueva-caracteristica`)
3. Realiza tus cambios y haz commit (`git commit -am 'Añadir nueva característica'`)
4. Haz push a la rama (`git push origin feature/nueva-caracteristica`)
5. Crea un Pull Request

## Licencia 📄

Este proyecto está licenciado bajo [incluir licencia aquí].

---

Desarrollado con ❤️ por [tu nombre/equipo]

