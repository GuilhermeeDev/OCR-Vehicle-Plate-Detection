import cv2 # type: ignore
import logging
import os
import shutil
import torch # type: ignore
import torch.nn as nn # type: ignore
import re
import itertools
import numpy as np # type: ignore
from collections import Counter
from datetime import datetime
from fastapi import FastAPI, File, UploadFile  # type: ignore
from fastapi.responses import JSONResponse     # type: ignore
from PIL import Image                          # type: ignore
from torchvision import models, transforms     # type: ignore
from paddleocr import PaddleOCR                # type: ignore
from inference_sdk import InferenceHTTPClient  # type: ignore
from fastapi.middleware.cors import CORSMiddleware # type: ignore
import mysql.connector # type: ignore
from mysql.connector import Error # type: ignore

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

@app.post("/")
def read_root():
    return {'Mensagem': 'Hello world'}

pasta_saida = "placas_identificadas"

def salvar_resultado_banco(nome_arquivo, resultado):
    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='',
            database='ocr_db'
        )
        cursor = conn.cursor()
        sql = "INSERT INTO resultados_ocr (nome_arquivo, resultado) VALUES (%s, %s)"
        cursor.execute(sql, (nome_arquivo, resultado))
        conn.commit()
        cursor.close()
        conn.close()
    except Error as e:
        logging.error(f"Erro ao salvar no banco: {e}")

def get_ocr(controle):
    configs = {
        0: lambda: PaddleOCR(use_angle_cls=True, lang='pt'),
        1: lambda: PaddleOCR(use_angle_cls=True, lang='ch'),
        2: lambda: PaddleOCR(use_angle_cls=True, lang='en'),
        3: lambda: PaddleOCR(use_angle_cls=True, lang='fr'),
        4: lambda: PaddleOCR(use_angle_cls=True, lang='it'),
        5: lambda: PaddleOCR(use_angle_cls=True, lang='ka')
    }
    return configs.get(controle, configs[0])()

def checar(texto):
    padrao_antigo_traco = r'^[A-Z]{3}-\d{4}$'  # Ex: ABC-1234
    padrao_antigo_sem_traco = r'^[A-Z]{3}\d{4}$'  # Ex: ABC1234
    padrao_novo = r'^[A-Z]{3}\d[A-Z]\d{2}$'  # Ex: ABC1D23

    if re.match(padrao_novo, texto):
        print(f"O texto '{texto}' corresponde ao padrão NOVO de placa.")
        return True

    if re.match(padrao_antigo_traco, texto) or re.match(padrao_antigo_sem_traco, texto):
        print(f"O texto '{texto}' corresponde ao padrão ANTIGO de placa.")
        return True
    
def verificar_padrao_placa(texto):
    texto = texto.upper().replace(' ', '')
    fase = checar(texto)
    if fase == True:
        return texto
    if fase == None:

        #Parte do tratamento de possiveis erros do OCR.
        # Se não encontrou, procura posições de 'O' e '0'
        indices_trocaveis = [i for i, c in enumerate(texto) if c in ['0', 'O']]
        
        if not indices_trocaveis:
            print(f"Nenhuma correspondência encontrada para '{texto}', e não há 'O' ou '0' para trocar.")
            return None

        # Gerar todas as combinações possíveis de troca
        possibilidades = []
        n = len(indices_trocaveis)
        
        # Cada combinação é uma sequência de 0 (não troca) ou 1 (troca)
        for bits in itertools.product([0,1], repeat=n):
            texto_lista = list(texto)
            for bit, idx in zip(bits, indices_trocaveis):
                if bit == 1:
                    # Troca O por 0 ou 0 por O
                    texto_lista[idx] = '0' if texto_lista[idx] == 'O' else 'O'
            nova_tentativa = ''.join(texto_lista)
            possibilidades.append(nova_tentativa)

        # Testa todas as combinações geradas
        for tentativa in possibilidades:
            if checar(tentativa) == True:
                return tentativa

        # Se nenhuma tentativa foi válida
        print(f"Nenhuma correspondência encontrada para '{texto}' após todas as tentativas de troca.")
        return None
  
def criar_pastas():
    pasta = "videos_servidor"
    pasta_2 = "frames_servidor"
    pasta_3 = "fotos_servidor"
    pasta_4 = "placas_identificadas"
    os.makedirs(pasta, exist_ok=True)
    os.makedirs(pasta_2, exist_ok=True)
    os.makedirs(pasta_3, exist_ok=True)
    os.makedirs(pasta_4, exist_ok=True)

def criar_pasta_do_video(video):
    try:
        nome_arquivo = os.path.basename(video)
        nome_pasta = os.path.splitext(nome_arquivo)[0]
        pasta_destino = os.path.join("frames_servidor", nome_pasta)

        if not os.path.exists(pasta_destino):
            os.makedirs(pasta_destino)
            print(f"Pasta '{nome_pasta}' criada com sucesso.")
        else:
            print(f"Pasta '{nome_pasta}' já existe.")

        return pasta_destino

    except Exception as e:
        logging.error(f"Erro ao criar a pasta para o vídeo '{video}': {e}")
        return None

def processar_e_salvar_crop(caminho_imagem, pasta_destino):
    try:
        # Inicializa o cliente da API Roboflow
        CLIENT = InferenceHTTPClient(
            api_url="https://detect.roboflow.com",
            api_key="FppS5gQx11lCWKuo4VNR"
        )
        
        # Faz a inferência via Roboflow
        result = CLIENT.infer(caminho_imagem, model_id="teste-eapur/1")
        
        if not result['predictions']:
            return {"message": "Nenhuma detecção encontrada."}

        # Pega a primeira detecção
        prediction = result['predictions'][0]

        # Abre a imagem
        img = Image.open(caminho_imagem)
        width, height = img.size

        # Obtém e converte coordenadas normalizadas para absolutas
        x = prediction['x']
        y = prediction['y']
        w = prediction['width']
        h = prediction['height']

        left = max(0, int(x - w / 2))
        top = max(0, int(y - h / 2))
        right = min(width, int(x + w / 2))
        bottom = min(height, int(y + h / 2))

        # Realiza o crop
        cropped_img = img.crop((left, top, right, bottom))

        # Define o nome e o caminho do arquivo de crop
        nome_crop = f"crop_{os.path.basename(caminho_imagem)}"
        caminho_crop = os.path.join(pasta_destino, nome_crop)

        # Salva o crop
        cropped_img.save(caminho_crop)

    except Exception as e:
        logging.error(f"Erro ao processar a imagem: {e}")
        return {"message": f"Erro: {str(e)}"}

def extrair_texto_placa(imagem_path,controle):
    try:     
        textos = []
        #ocr muda de acordo com a variavel controle
        ocr = get_ocr(controle)
        
        imagem = cv2.imread(imagem_path)
        if imagem is None:
            print(f"[ERRO] Não foi possível carregar a imagem: {imagem_path}")
            return None
        resultado = ocr.ocr(imagem, det=True, rec=True, cls=True)
        
        # Percorre até 4 caixas de texto
        for linha in resultado:
            for caixa in linha:
                texto = caixa[1][0]
                if texto:
                    verificador = verificar_padrao_placa(texto)
                    if verificador != None:
                        textos.append(verificador)
                if len(textos) >= 4:       # já temos 4, interrompe tudo
                    break
            if len(textos) >= 4:
                break
        return textos
    except Exception as e:
        print(f"[ERRO] Falha ao extrair texto com PaddleOCR: {e}")
        return None

def inferencia_placa(pasta_imagens):
    try:
        controle = 0
        resultados_texto = []
        contador_imagens = 0
        imagens = [f for f in os.listdir(pasta_imagens) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        pasta_destino = os.path.join(pasta_saida, pasta_imagens)
        
        if not os.path.exists(pasta_destino):
            os.makedirs(pasta_destino)
            print(f"Pasta de crop '{pasta_destino}' criada com sucesso.")
        else:
            print(f"Pasta de crop '{pasta_destino}' já existe.")
            
        for nome_imagem in imagens:
            caminho_imagem = os.path.join(pasta_imagens, nome_imagem)
            imagem = cv2.imread(caminho_imagem)
            if imagem is None:
                logging.warning(f"Imagem inválida (None): {caminho_imagem}")
                continue

            processar_e_salvar_crop(caminho_imagem, pasta_destino)
            
        imagens_placas = [f for f in os.listdir(pasta_destino) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

        # Realiza o OCR em todas as imagens
        for nome_imagem in imagens_placas:
            caminho_imagem = os.path.join(pasta_destino, nome_imagem)
            print(f"[INFO] Realizando OCR na imagem: {caminho_imagem}")

            resultado = extrair_texto_placa(caminho_imagem,controle)

            if not resultado:
                print(f"Realizando variações do OCR com o controle: {controle}")
                for controle in range(7):
                    resultado_ = extrair_texto_placa(caminho_imagem, controle)
                    if resultado_:
                        resultado = resultado_
                        break
                      
            if resultado:
                for texto in resultado:
                    resultados_texto.append(texto)
                    contador_imagens += 1
                    print(f"[INFO] Texto extraído: {texto}")
            else:
                print(f"[INFO] Nenhum texto extraído da imagem: {nome_imagem}")
        # Conta a frequência de cada resultado
        contagem = Counter(resultados_texto)
        if contagem:
            resultado_final = contagem.most_common(1)[0][0]
        else:
            resultado_final = "Nenhuma placa identificada"

        print(f"[RESULTADO FINAL] Resultado mais fiel: {resultado_final}")

        salvar_resultado_banco(pasta_imagens, resultado_final)
        
        return resultado_final

    except Exception as e:
        logging.error(f"Erro na inferência de placas: {e}")
        return None

def extrai_frames(video):
    try:
        nome_video = video
        pasta = criar_pasta_do_video(nome_video)

        if not pasta:
            logging.error("Falha ao criar pasta para o vídeo.")
            return None

        video_cap = cv2.VideoCapture(video)
        cont = 0

        while video_cap.isOpened():
            verificador, frame = video_cap.read()

            if verificador:
                cv2.imwrite(os.path.join(pasta, f"{cont}.png"), frame)
                cont += 1
            else:
                break

        cv2.destroyAllWindows()
        video_cap.release()

        return pasta
    
    except Exception as e:
        logging.error(f"Não foi possível gerar os frames para o vídeo '{video}': {e}")
        return None
    
@app.post("/video/")
async def video(video: UploadFile = File(...)):
    try:
        criar_pastas()
        
        if not video.filename.endswith(('.mp4', '.mov', '.avi', '.mkv')):
            return JSONResponse(status_code=400, content={"message": "Formato de video não suportado"})

        temp_dir = "videos_servidor"
        video_path = os.path.join(temp_dir, video.filename)

        with open(video_path, "wb") as buffer:
            shutil.copyfileobj(video.file, buffer)

        #chama a funcao extrai_frames passando o video_path
        fluxo = extrai_frames(video_path)
        resultado_final = inferencia_placa(fluxo)
        return {"Resultado mais frequente": resultado_final}

    except Exception as e:
        logging.error(f"Erro ao receber o video e realizar os frames!: {e}")
        return JSONResponse(status_code=500, content={"message": f"Erro: {str(e)}"})

@app.post("/foto/")
async def foto(foto: UploadFile = File(...)):
    try:
        criar_pastas()
        
        if not foto.filename.endswith(('.png', '.jpg', '.jpeg', '.webp')):
            return JSONResponse(status_code=399, content={"message": "Formato de foto não suportado"})

        temp_dir = "fotos_servidor"
        nome_pasta = os.path.splitext(foto.filename)[0]
        pasta_destino = os.path.join(temp_dir, nome_pasta)
        os.makedirs(pasta_destino, exist_ok=True)

        foto_path = os.path.join(pasta_destino, foto.filename)

        # Salva a imagem
        with open(foto_path, "wb") as buffer:
            shutil.copyfileobj(foto.file, buffer)

        # Chama a inferência passando o caminho da pasta onde está a imagem
        resultado = inferencia_placa(pasta_destino)

        return {"Resultado da placa": resultado}

    except Exception as e:
        logging.error(f"Erro ao receber a imagem: {e}")
        return JSONResponse(status_code=500, content={"message": f"Erro: {str(e)}"})

@app.get("/resultados/")
def listar_resultados():
    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='',
            database='ocr_db'
        )
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT nome_arquivo, resultado, data_hora FROM resultados_ocr ORDER BY data_hora DESC")
        resultados = cursor.fetchall()
        cursor.close()
        conn.close()
        return resultados
    except Exception as e:
        logging.error(f"Erro ao buscar resultados: {e}")
        return JSONResponse(status_code=500, content={"message": str(e)})
    
#python -m uvicorn main:app --reload --port 8000

# PS .venv\Scripts\Activate.ps1
# CMD .venv\Scripts\activate
