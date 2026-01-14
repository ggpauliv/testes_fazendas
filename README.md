# 🌱 AgroTalhoes - Sistema de Gestão de Fazendas

Sistema completo para gestão de talhões agrícolas, controle de estoque, importação de NFe e análise de custos/ROI.

## 🛠️ Pré-requisitos

- Python 3.10+
- SQL Server Express (localhost\SQLEXPRESS)
- ODBC Driver 17 for SQL Server

---

## 📦 Instalação Passo a Passo

### 1. Criar o Banco de Dados no SQL Server

Abra o **SQL Server Management Studio (SSMS)** e execute:

```sql
CREATE DATABASE db_talhoes;
GO
```

### 2. Instalar o ODBC Driver 17 for SQL Server

1. Acesse: https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server
2. Baixe o **"ODBC Driver 17 for SQL Server"** para Windows
3. Execute o instalador e siga as instruções
4. Reinicie o computador após a instalação

### 3. Criar o Ambiente Virtual Python

```powershell
# Navegue até a pasta do projeto
cd "c:\Users\useer\Projetos\gestor talhao"

# Crie o ambiente virtual
python -m venv venv

# Ative o ambiente virtual
.\venv\Scripts\Activate.ps1

# Instale as dependências
pip install -r requirements.txt
```

### 4. Configurar as Variáveis de Ambiente (Opcional)

Crie um arquivo `.env` na raiz do projeto se preferir usar autenticação SQL:

```env
DB_USER=seu_usuario
DB_PASSWORD=sua_senha
USE_TRUSTED_CONNECTION=no
```

### 5. Executar as Migrações

```powershell
python manage.py makemigrations
python manage.py migrate
```

### 6. Criar Superusuário

```powershell
python manage.py createsuperuser
```

### 7. Executar o Servidor de Desenvolvimento

```powershell
python manage.py runserver
```

Acesse: http://127.0.0.1:8000

---

## 🗂️ Estrutura do Projeto

```
gestor talhao/
├── agrotalhoes/           # Configurações do projeto Django
│   ├── settings.py        # Configurações (incluindo conexão SQL Server)
│   ├── urls.py
│   └── wsgi.py
├── core/                  # App principal
│   ├── models.py          # Modelos de dados
│   ├── views.py           # Views/Controllers
│   ├── urls.py            # Rotas da aplicação
│   ├── utils/             # Utilitários
│   │   └── nfe_parser.py  # Parser de XML NFe
│   └── templates/         # Templates HTML
├── static/                # Arquivos estáticos
├── requirements.txt       # Dependências Python
└── manage.py
```

---

## 🔑 Funcionalidades Principais

- **📍 Gestão de Talhões:** Desenho de polígonos no Google Maps
- **📦 Controle de Estoque:** Entrada/Saída de produtos
- **📄 Importação NFe:** Parse automático de XML
- **📊 Dashboard ROI:** Análise de custos e lucros

---

## 🔒 Configuração de Autenticação

### Autenticação Windows (Trusted Connection)
Por padrão, o sistema usa autenticação Windows. Nenhuma configuração adicional é necessária.

### Autenticação SQL Server
Edite o arquivo `.env` conforme indicado na seção 4.

---

## 🗺️ Google Maps API

Para usar o mapa, obtenha uma API Key:
1. Acesse: https://console.cloud.google.com/
2. Crie um projeto e ative a "Maps JavaScript API"
3. Adicione a chave no arquivo `settings.py` em `GOOGLE_MAPS_API_KEY`

---

## 📝 Licença

Projeto desenvolvido para uso interno.
