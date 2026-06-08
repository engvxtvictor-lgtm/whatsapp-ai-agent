import httpx
from backend.system.config import settings
from backend.system.logger import logger

async def send_message(phone: str, text: str, reply_jid: str = None) -> bool:
    """Envia mensagem de texto. reply_jid é o JID completo (@lid ou @s.whatsapp.net) para roteamento."""
    if phone != settings.HUMAN_PHONE:
        try:
            from backend.agent.services import session as sess
            session = await sess.get_session(phone)
            session = await sess.add_to_history(session, "assistant", text)
            await sess.save_session(phone, session)
        except Exception as e:
            logger.error(f"Erro ao salvar mensagem no historico do Redis: {e}")

    # Usa o reply_jid completo (pode ser @lid) se disponível, senão usa o phone limpo
    destination = reply_jid if reply_jid else phone

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            url = f"{settings.WHATSAPP_API_URL}/send"
            r = await client.post(url, json={"phone": destination, "text": text})
            logger.info(f"Mensagem enviada para {phone[:6]}*** (jid={destination})")
            return r.status_code == 200
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem: {e}")
            return False


async def send_document(phone: str, pdf_url: str, filename: str = "tabela_servicos.pdf", caption: str = "", reply_jid: str = None) -> bool:
    """Envia um documento PDF via WhatsApp. reply_jid é o JID completo para roteamento."""
    if phone != settings.HUMAN_PHONE:
        try:
            from backend.agent.services import session as sess
            session = await sess.get_session(phone)
            session = await sess.add_to_history(session, "assistant", f"[📎 Documento Anexado: {filename}]\n{caption}")
            await sess.save_session(phone, session)
        except Exception as e:
            logger.error(f"Erro ao salvar documento no historico do Redis: {e}")

    destination = reply_jid if reply_jid else phone

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            url = f"{settings.WHATSAPP_API_URL}/send-document"
            payload = {
                "phone": destination,
                "url": pdf_url,
                "filename": filename,
                "caption": caption
            }
            r = await client.post(url, json=payload)
            logger.info(f"Documento enviado para {phone[:6]}*** (jid={destination})")
            return r.status_code == 200
        except Exception as e:
            logger.error(f"Erro ao enviar documento: {e}")
            return False


async def send_escalation(phone: str, reply_jid: str = None):
    await send_message(phone,
        "Vou te transferir para um atendente agora. Aguarde um momento! 🙏",
        reply_jid=reply_jid
    )


async def notify_agent(user_phone: str, message: str, history: list = None):
    text = f"🔔 *Nova escalação*\n\n*Cliente:* {user_phone}\n*Link Rápido:* https://wa.me/{user_phone}\n*Última Mensagem:* _{message}_"
    
    if history:
        text += "\n\n*Últimas mensagens da conversa:*\n"
        # Pega as últimas 6 mensagens para dar contexto ao atendente
        recent_history = [msg for msg in history if msg["role"] in ["user", "assistant"]][-6:]
        for msg in recent_history:
            role = "👤 Cliente" if msg["role"] == "user" else "🤖 IA"
            # Limpa quebras de linha para ficar mais legível
            content = msg["content"].replace('\n', ' ').strip()
            # Limita tamanho da mensagem no histórico para evitar textos gigantes
            if len(content) > 150:
                content = content[:147] + "..."
            text += f"{role}: {content}\n"
            
    await send_message(settings.HUMAN_PHONE, text)
