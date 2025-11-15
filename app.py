from flask import Flask, render_template, request, session, Response
import requests
from flask_cors import CORS
import uuid
import json
import traceback

app = Flask(__name__)
app.secret_key = "qualquer_coisa_aqui"
CORS(app)

SYSTEM_PROMPT = """
Você é ASTRA, um oráculo digital que combina filosofia existencial, psicologia simbólica, mitologia, tarot e astrologia.

IMPORTANTE:
Você NUNCA deve explicar sua classificação, nem mencionar que está seguindo categorias. 
Você deve APENAS responder no estilo adequado conforme o tipo de pergunta do usuário.

Use esta lógica INTERNAMENTE:

A) Pergunta objetiva
Exemplos: “qual meu signo?”, “quem rege libra?”, “o que é vênus?”
→ Resposta curta, direta, clara e elegante.
→ Nada de poesia. Nada de excesso.
→ Nunca inventar informação astrológica.

B) Pergunta existencial / emocional / espiritual
Exemplos: “por que estou perdido?”, “qual o sentido da vida?”
→ Resposta poética, acolhedora, simbólica, introspectiva.
→ Metáforas cósmicas, mas sem enrolação.

C) Pergunta híbrida
Exemplos: “o que é mercúrio retrógrado pra mim?”, “estou em saturno?”
→ Resposta clara + simbólica.
→ Leve poesia, mas moderada.
→ Mistura de explicação objetiva com interpretação simbólica.

REGRAS CENTRAIS:
- Não explique o processo, apenas responda.
- Não mencione categorias.
- Não comece respostas objetivas com metáforas.
- Não invente correspondências astrológicas.
- Nunca diga limitações do tipo “sou só uma IA”.
- Nada de previsões literais de futuro — apenas simbolismo.
- Sempre responda com naturalidade, fluidez e elegância.

Sua única função é: ler a pergunta, identificar internamente o tipo, e responder no tom correto.
"""


MODEL = "qwen2.5:1.5b"   # modelo leve e rápido para 4 GB de RAM


# ----------------------------------------------------------
#  STREAM COM OLLAMA (LOCAL)
# ----------------------------------------------------------
def stream_qwen(prompt):
    print("[DEBUG] Chamando Qwen via Ollama...")

    url = "http://localhost:11434/api/generate"
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": True
    }

    try:
        response = requests.post(url, json=payload, stream=True)
    except Exception:
        print("[ERRO] Não conseguiu conectar ao Ollama.")
        yield "[ERRO] Ollama não está rodando."
        return

    if response.status_code != 200:
        print("[ERRO] Ollama retornou:", response.text)
        yield "[ERRO] Modelo não pôde responder."
        return

    for line in response.iter_lines():
        if not line:
            continue
        try:
            data = json.loads(line.decode("utf-8"))
            chunk = data.get("response", "")
            print("[DEBUG CHUNK]:", chunk)
            yield chunk
        except Exception as e:
            print("[ERRO JSON]", e)
            continue


# ----------------------------------------------------------
#  ROTAS
# ----------------------------------------------------------
@app.route("/")
def index():
    if "chat_id" not in session:
        session["chat_id"] = str(uuid.uuid4())

    if "history" not in session:
        session["history"] = []

    return render_template("index.html")


@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.json
        user_msg = data.get("question", "").strip()

        print("[DEBUG] Usuário disse:", user_msg)

        # prepara histórico na forma de texto concatenado
        history = session.get("history", [])

        history_text = SYSTEM_PROMPT + "\n\n"

        for msg in history:
            history_text += f"Usuário: {msg['user']}\nASTRA: {msg['bot']}\n"

        history_text += f"Usuário: {user_msg}\nASTRA: "

        def generate():
            bot_text = ""

            try:
                for chunk in stream_qwen(history_text):
                    bot_text += chunk
                    yield chunk

            except Exception:
                print("[ERRO STREAMING]:", traceback.format_exc())
                yield "[ERRO durante streaming]"

            # salva histórico
            history.append({"user": user_msg, "bot": bot_text})
            session["history"] = history
            print("[DEBUG] Histórico atualizado:", history)

        return Response(generate(), mimetype="text/plain")

    except Exception:
        print("[ERRO] Falha /ask:", traceback.format_exc())
        return {"error": "Erro interno"}, 500


@app.route("/save_history", methods=["POST"])
def save_history():
    data = request.json
    user = data["user"]
    bot = data["bot"]

    history = session.get("history", [])
    history.append({"user": user, "bot": bot})
    session["history"] = history

    return {"status": "ok"}


if __name__ == "__main__":
    app.run(debug=True)
