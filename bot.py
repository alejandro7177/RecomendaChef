import logging
import tempfile
import io
from telegram import Update
from telegram.ext import filters, MessageHandler, ApplicationBuilder, CommandHandler, ContextTypes, ConversationHandler
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage
import os
from graph import Orquetador

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

ASKING_PRODUCT_FOR_QUANTITY, ASKING_NEW_QUANTITY = range(2)

class TelegramBot:

    def __init__(
            self, 
            agent_orchestrator: Orquetador,
            orchestrator_prompt: str,
            start_text: str = "Soy el testbot!",
            ):
        
        self.agent_orchestrator = agent_orchestrator
        self.orchestrator_prompt = orchestrator_prompt
        self.start_text = start_text
        self.messages: list = []

     # --- Handler for /inventario ---
    async def show_inventory(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handles the /inventario command, showing current inventory."""
        chat_id = update.effective_chat.id
        logging.info(f"Command /inventario received from chat {chat_id}")
        try:
            # Get data from the orchestrator (which should query the DB)
            inventory_data = self.agent_orchestrator.get_inventory_data()

            print(f"Inventory data: {inventory_data}")  # Debugging line
            if not inventory_data:
                await context.bot.send_message(chat_id=chat_id, text="Tu inventario está vacío.")
                return

            # Format the inventory data for display
            inventory_list_text = "Tu Inventario Actual:\n"
            inventory_list_text += "\n"
            for product in inventory_data:
                # Adjust formatting based on the actual data structure returned
                id_producto = product.get('id_producto', 'N/A')
                name = product.get('nombre_producto', 'N/A')
                cantidad = product.get('cantidad', '')
                u_medida = product.get('unidad_medida', 'N/A')
                fecha_vencimiento = product.get('fecha_vencimiento', 'N/A')
                inventory_list_text += f"- {id_producto}) {name}: {cantidad} {u_medida} || {fecha_vencimiento if fecha_vencimiento else 'no expire'}\n"

            await context.bot.send_message(chat_id=chat_id, text=inventory_list_text)
        except Exception as e:
            logging.error(f"Error fetching/displaying inventory: {e}", exc_info=True)
            await context.bot.send_message(chat_id=chat_id, text="Lo siento, ocurrió un error al obtener el inventario.")

    # Start command handler
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(chat_id=update.effective_chat.id, text=self.start_text)

    # --- Handlers for /update_inv Conversation ---
    async def cantidad_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Starts the /update_inv conversation, asks for product name."""
        chat_id = update.effective_chat.id
        logging.info(f"Command /update_inv received from chat {chat_id}, starting conversation.")
        await update.message.reply_text(
            "De acuerdo. ¿De qué producto quieres actualizar el stock?\n"
            "Escribe el nombre exacto (o /cancelar para salir)."
        )
        # Transition to the state where we expect the product name
        return ASKING_PRODUCT_FOR_QUANTITY

    async def cantidad_received_product(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handles receiving the product name during the /update_inv conversation."""
        chat_id = update.effective_chat.id
        product_name = update.message.text.strip()
        logging.info(f"Received product name '{product_name}' for /update_inv from chat {chat_id}.")

        # Check if product exists using the orchestrator
        try:
            exists = self.agent_orchestrator.check_product_exists(product_name)
            if exists:
                # Store the product name for the next step
                context.user_data['product_to_update'] = product_name
                logging.info(f"Product '{product_name}' found. Asking for new quantity.")
                await update.message.reply_text(
                    f"¡Entendido! ¿Cuál es la nueva cantidad para descontar stock de '{product_name}'?\n"
                    "Escribe sólo el número (o /cancelar)."
                )
                # Transition to the state where we expect the new quantity
                return ASKING_NEW_QUANTITY
            else:
                logging.warning(f"Product '{product_name}' not found in inventory for chat {chat_id}.")
                await update.message.reply_text(
                    f"Lo siento, no encontré '{product_name}' en tu inventario.\n"
                    "Puedes usar /inventario para ver los productos disponibles.\n"
                    "La operación ha sido cancelada."
                )
                # End the conversation
                context.user_data.pop('product_to_update', None) # Clear data
                return ConversationHandler.END
        except Exception as e:
            logging.error(f"Error checking product existence for '{product_name}': {e}", exc_info=True)
            await update.message.reply_text("Hubo un error verificando el producto. Intenta de nuevo más tarde.")
            context.user_data.pop('product_to_update', None) # Clear data
            return ConversationHandler.END


    async def cantidad_received_quantity(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handles receiving the new quantity during the /update_inv conversation."""
        chat_id = update.effective_chat.id
        new_quantity_text = update.message.text.strip()
        product_name = context.user_data.get('product_to_update')

        if not product_name:
            logging.warning(f"Received quantity '{new_quantity_text}' but no product stored in context for chat {chat_id}.")
            await update.message.reply_text("Algo salió mal, no recuerdo qué producto estábamos actualizando. Por favor, inicia de nuevo con /update_inv.")
            return ConversationHandler.END

        logging.info(f"Received quantity '{new_quantity_text}' for product '{product_name}' from chat {chat_id}.")

        # Validate if the quantity is a number
        try:
            new_quantity = float(new_quantity_text) # Use float to allow decimals if needed, or int()
            if new_quantity < 0: # Optional: prevent negative quantities
                 raise ValueError("Quantity cannot be negative.")

            # Update the quantity using the orchestrator
            success = self.agent_orchestrator.update_inventory_quantity(product_name, new_quantity)

            if success:
                logging.info(f"Successfully updated quantity for '{product_name}' to {new_quantity} for chat {chat_id}.")
                await update.message.reply_text(
                    f"¡Perfecto! La cantidad de '{product_name}' ha sido actualizada!"
                )
            else:
                # This case might be redundant if check_product_exists worked, but good for safety
                logging.error(f"Orchestrator failed to update quantity for '{product_name}' (maybe removed between steps?).")
                await update.message.reply_text(f"No se pudo actualizar '{product_name}'. ¿Quizás fue eliminado? Verifica con /inventario.")

            # End the conversation successfully
            context.user_data.pop('product_to_update', None) # Clean up context
            return ConversationHandler.END

        except ValueError:
            logging.warning(f"Invalid quantity format '{new_quantity_text}' received from chat {chat_id}.")
            await update.message.reply_text(
                "Eso no parece un número válido. Por favor, introduce sólo la cantidad numérica (ej: 500 o 1.5).\n"
                "O escribe /cancelar para salir."
            )
            # Stay in the same state to allow user to retry
            return ASKING_NEW_QUANTITY
        except Exception as e:
            logging.error(f"Error updating quantity for '{product_name}': {e}", exc_info=True)
            await update.message.reply_text("Hubo un error al actualizar la cantidad. Intenta de nuevo más tarde.")
            context.user_data.pop('product_to_update', None) # Clean up context
            return ConversationHandler.END

    async def cantidad_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancels the /update_inv conversation."""
        chat_id = update.effective_chat.id
        logging.info(f"Conversation /update_inv cancelled by user from chat {chat_id}.")
        await update.message.reply_text('Operación cancelada.')
        # Clean up any stored data
        context.user_data.pop('product_to_update', None)
        return ConversationHandler.END

    async def text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.messages.append(HumanMessage(content=update.message.text))
        message = self.agent_orchestrator.invoke_agents(self.messages)
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text=message.content if isinstance(message, BaseMessage) else "Error: No content",
        )
        self.messages.append(message)


    def run(self, token: str = None):

        if token is None:
            token = os.environ['TELEGRAM_BOT_TOKEN']

        application = ApplicationBuilder().token(token).build()

        start_handler = CommandHandler('start', self.start)
        text_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), self.text)
        inventory_handler = CommandHandler('inventario', self.show_inventory)
        cantidad_conv_handler = ConversationHandler(
            entry_points=[CommandHandler('update_inv', self.cantidad_start)],
            states={
                ASKING_PRODUCT_FOR_QUANTITY: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.cantidad_received_product)
                ],
                ASKING_NEW_QUANTITY: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.cantidad_received_quantity)
                ],
            },
            fallbacks=[CommandHandler('cancelar', self.cantidad_cancel)], # Use /cancelar
            # Optional: Add timeouts, persistence, etc.
        )

        application.add_handler(cantidad_conv_handler)


        application.add_handler(start_handler)
        application.add_handler(text_handler)
        application.add_handler(inventory_handler)

        application.run_polling()
