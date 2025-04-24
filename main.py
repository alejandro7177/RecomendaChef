from graph import Orquetador, graph
from bot import TelegramBot

if __name__ == "__main__":
    # Initialize the bot with the agent orchestrator and prompt
    orquestador = Orquetador()
    graph()
    bot = TelegramBot(
        agent_orchestrator=orquestador,
        orchestrator_prompt="Soy un bot de inventario, puedo ayudarte a gestionar tu inventario.",
        start_text="Hola! Soy un bot recomenda Chef. ¿En qué puedo ayudarte?",
    )
    
    # Run the bot with the provided token
    bot.run()