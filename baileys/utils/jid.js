/**
 * Resolve JIDs e obtém o número de telefone do remetente.
 * Trata JIDs antigos e o novo formato @lid, buscando sempre um número normalizado.
 *
 * @param {Object} msg - Mensagem recebida no upsert.
 * @param {Object} sock - Instância do socket Baileys.
 * @returns {Object} - Objeto contendo o rawJid e o resolvedPhone.
 */
function getSenderNumber(msg, sock) {
  // Temporary log for debugging
  console.log("msg.key:", JSON.stringify(msg.key, null, 2));

  // The JID that sent the message. For groups, it's participant. For DMs, remoteJid.
  const rawJid = msg.key.remoteJid;

  // By default, assume the normalized phone is the rawJid
  let normalizedPhone = rawJid;

  // Handle @lid logic
  if (rawJid && rawJid.includes('@lid')) {
    if (msg.key.senderPn) {
      // Latest Baileys version might provide senderPn natively for @lid contacts
      normalizedPhone = msg.key.senderPn;
      console.log(`✅ LID resolvido via senderPn: ${rawJid} → ${normalizedPhone}`);
    } else if (sock && sock.signalRepository && sock.signalRepository.lidMapping) {
      // Try fallback to lidMapping
      const resolved = sock.signalRepository.lidMapping.getPNForLID(rawJid);
      if (resolved) {
        normalizedPhone = resolved;
        console.log(`✅ LID resolvido via lidMapping: ${rawJid} → ${normalizedPhone}`);
      }
    }
    
    // If we still only have the LID, we mark it as unresolved but we don't crash
    if (normalizedPhone === rawJid) {
      console.log(`⚠️  Não foi possível resolver LID de forma nativa: ${rawJid}`);
    }
  }

  // Clean the phone number to be purely numeric (or a LID string if unresolved)
  // This removes suffixes like @s.whatsapp.net, @lid, @c.us, @g.us
  const phone = normalizedPhone ? normalizedPhone.replace(/@.*$/, "") : "";

  return {
    rawJid: rawJid,
    resolvedPhone: phone
  };
}

module.exports = { getSenderNumber };
