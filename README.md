# OCR-Vehicle-Plate-Detection
O **OCR-Vehicle-Plate-Detection** é uma aplicação fullstack que permite a detecção automática de placas de veículos, realizando OCR (Reconhecimento Óptico de Caracteres), salvando resultados em um banco de dados MySQL local e exibindo tudo em uma interface web. Para qualquer duvida conceitual ou tecnica [acesse a documentação completa](./docs/documentacao.md). 

---
### Funcionalidades principais:

- Upload de **imagens** ou **vídeos** via aplicação front-end ou metodo **POST**  
- Detecção da área da placa via **Roboflow API**
- Reconhecimento de texto com **PaddleOCR**  
- Filtragem de ruído e correção de erros de caracter
- Validação do padrão de placas brasileiras
- Armazenamento dos resultados (arquivo, resultado, data/hora) em banco de dados local
- Exibição dos resultados diretamente na interface web
---

### Tecnologias usadas:

| Camada        | Tecnologia                          |
|---------------|-------------------------------------|
| Backend API   | FastAPI (Python 3.8)                |
| OCR           | PaddleOCR                           |
| Detector      | Roboflow Hosted API (YOLOv8)        |
| Banco de Dados| MySQL via XAMPP                     |
| Frontend      | HTML + CSS + JavaScript (Fetch API) |

---
### Dependências
- Python 3.8
---

### Como executar localmente:

1.  Clone este repositório.  
```bash
git clone https://github.com/GuilhermeeDev/OCR-Vehicle-Plate-Detection.git
```

2.  Baixe as bibliotecas utilizadas na aplicação.
```bash
cd OCR-Vehicle-Plate-Detection
pip --version
pip install -r requirements.txt
```

