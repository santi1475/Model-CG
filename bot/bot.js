const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const axios = require('axios');
const fs = require('fs');
const path = require('path');

const API_URL = process.env.API_URL || 'http://localhost:8000';

const client = new Client({
    authStrategy: new LocalAuth({ dataPath: '/app/session' }),
    puppeteer: { 
        args: ['--no-sandbox', '--disable-setuid-sandbox'],
        headless: true
    }
});

client.on('qr', qr => {
    console.log('Escanea este QR con WhatsApp:');
    qrcode.generate(qr, { small: true });
});

client.on('ready', () => {
    console.log('Bot conectado y listo');
});

client.on('message', async msg => {
    // Solo procesar mensajes con imagen
    if (!msg.fromMe) return;

    const media = await msg.downloadMedia();
    if (!media.mimetype.startsWith('image/')) return;

    console.log(`Imagen recibida de ${msg.from}`);
    await msg.reply('Procesando imagen de balanza...');

    try {
        // Convertir base64 a buffer
        const buffer = Buffer.from(media.data, 'base64');
        const tmpPath = `/tmp/balanza_${Date.now()}.jpg`;
        fs.writeFileSync(tmpPath, buffer);

        // Enviar a FastAPI
        const formData = new FormData();
        const blob = new Blob([buffer], { type: media.mimetype });
        formData.append('file', blob, 'balanza.jpg');

        const response = await axios.post(
            `${API_URL}/api/procesar-imagen`,
            formData,
            { headers: { 'Content-Type': 'multipart/form-data' } }
        );

        const { peso, precio, total } = response.data;

        // Respuesta formateada
        const respuesta = `✅ *Lectura de balanza*\n\n` +
            `⚖️ Peso: *${peso} kg*\n` +
            `💰 Precio: *S/ ${precio}/kg*\n` +
            `🧾 Total: *S/ ${total}*`;

        await msg.reply(respuesta);

        // Limpiar archivo temporal
        fs.unlinkSync(tmpPath);

    } catch (error) {
        console.error('Error:', error.message);
        await msg.reply('❌ No pude leer la imagen. Asegúrate que se vea bien la balanza.');
    }
});

client.initialize();