from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
    filters,
    CommandHandler
)
from PIL import Image
import pytesseract
import sqlite3
import datetime
import re
import os
import asyncio
import pytz

# =========================
# CONFIGURAÇÕES
# =========================

TOKEN = "8954940101:AAE5dYG70Ur3RYbVteSnGueCKY2gA0UHMsM"

# ID DO GRUPO
# coloque o ID do grupo aqui
GRUPO_ID = -5192063045

# caminho do tesseract no windows
# pytesseract.pytesseract.tesseract_cmd = (r"C:\Program Files\Tesseract-OCR\tesseract.exe")

# =========================
# BANCO SQLITE
# =========================

conn = sqlite3.connect("dados.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS registros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prontos TEXT,
    trabalho TEXT,
    missao TEXT,
    data TEXT,
    hora TEXT
)
""")

conn.commit()

# =========================
# EXTRAIR DADOS
# =========================

def extrair_dados(texto):

    print("======== TEXTO OCR ========")
    print(texto)
    print("===========================")

    # limpa espaços
    texto = re.sub(r"\s+", " ", texto)

    # pega números e horários
    itens = re.findall(
        r"\d{1,2}:\d{2}|\d+",
        texto
    )

    print(itens)

    horario = None
    numeros = []

    for item in itens:

        if ":" in item:
            horario = item
        else:
            numeros.append(item)

    if len(numeros) >= 2 and horario:

        prontos = numeros[0]
        trabalho = numeros[1]
        missao = horario

        if trabalho == "7":
            trabalho = "1"

        return prontos, trabalho, missao

    return "N/A", "N/A", "N/A"

# =========================
# RECEBER FOTO
# =========================

async def receber_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):

    foto = update.message.photo[-1]

    file = await context.bot.get_file(foto.file_id)

    os.makedirs("imagens", exist_ok=True)

    caminho_imagem = f"imagens/{foto.file_id}.jpg"

    await file.download_to_drive(caminho_imagem)

    # abrir imagem
    imagem = Image.open(caminho_imagem)

    # =========================
    # CORTAR ÁREA DOS STATUS
    # =========================

    # (esquerda, topo, direita, baixo)

    area = (2, 133, 583, 260)

    imagem = imagem.crop(area)
    # imagem.show() #mostrar imagem na tela do pc

    # preto e branco
    imagem = imagem.convert("L")

    # aumenta contraste
    # aumenta contraste sem destruir números
    from PIL import ImageEnhance

    contraste = ImageEnhance.Contrast(imagem)

    imagem = contraste.enhance(2)

    # aumenta tamanho
    imagem = imagem.resize(
        (imagem.width * 3, imagem.height * 3)
    )

    # OCR
    config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789:'

    texto = pytesseract.image_to_string(
        imagem,
        config=config
    )

    print(texto)

    # extrair dados
    prontos, trabalho, missao = extrair_dados(texto)

    # data e hora
    agora = datetime.datetime.now()

    data = agora.strftime("%d/%m/%Y")
    hora = agora.strftime("%H:%M:%S")

    # salvar no banco
    cursor.execute("""
    INSERT INTO registros
    (prontos, trabalho, missao, data, hora)
    VALUES (?, ?, ?, ?, ?)
    """, (prontos, trabalho, missao, data, hora))

    conn.commit()

    # mensagem
    mensagem = f"""
    🚀 *GERENCIAMENTO DE HORAS - YGOR*

    Finalizando o plantão em `{data}` às `{hora}`, com os seguintes indicadores operacionais:

    ┌─────────────────────┐
    │ 🟢 Scooters bipadas: `{prontos}`
    │ 🛠 Scooters em trabalho: `{trabalho}`
    │ 🚀 Em missão: `{missao}`
    └─────────────────────┘

    ✅ Plantão encerrado com monitoramento concluído.

    👤 *Ygor Alves de Oliveira*
    🛡 *Ranger*
    📅 *{data}*
    """

    # responder no grupo
    await context.bot.send_message(
        chat_id=GRUPO_ID,
        text=mensagem,
        parse_mode="Markdown"
    )

    # responder pra você
    await update.message.reply_text("🟢 Imagem analisada com sucesso!\n\n🧾 Verifique o canal de gerenciamento para ver as informações.")

async def historico(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    cursor.execute("""
    SELECT data, missao
    FROM registros
    ORDER BY id DESC
    LIMIT 10
    """)

    resultados = cursor.fetchall()

    if not resultados:

        await update.message.reply_text(
            "Nenhum registro encontrado."
        )

        return

    mensagem = "📊 *CONSULTA DE HORAS - WCMA*\n\n"

    for data, missao in reversed(resultados):

        # pega só dia/mês
        data_formatada = (
            datetime.datetime.strptime(
                data,
                "%d/%m/%Y"
            ).strftime("%d/%m")
        )

        mensagem += (
            f"📅 `{data_formatada}`"
            f" - 🚀 `{missao}`\n"
        )

    await update.message.reply_text(
        mensagem,
        parse_mode="Markdown"
    )

# =========================
# LEMBRETE 19H
# =========================

async def lembrete_turno(app):

    while True:

        agora = datetime.datetime.now(
            pytz.timezone("America/Sao_Paulo")
        )

        hora = agora.strftime("%H:%M")

        # 19:00
        if hora == "19:00":

            mensagem = """
🚨 *LEMBRETE DE ENCERRAMENTO*

Está na hora de finalizar o plantão.

📸 Envie a imagem do relatório operacional do turno para registrar as estatísticas do dia.
"""

            await app.bot.send_message(
                chat_id=GRUPO_ID,
                text=mensagem,
                parse_mode="Markdown"
            )

            # espera 60 segundos
            # para não enviar várias vezes
            await asyncio.sleep(60)

        await asyncio.sleep(20)

# =========================
# INICIAR BOT
# =========================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(
    MessageHandler(filters.PHOTO, receber_foto)
)

app.add_handler(
    CommandHandler(
        "historico",
        historico
    )
)

loop = asyncio.get_event_loop()

loop.create_task(
    lembrete_turno(app)
)

print("BOT ONLINE 🚀")

app.run_polling()