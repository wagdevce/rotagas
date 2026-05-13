#!/bin/bash

# --- Script de Construção Estruturado para Vercel ---
# Este ficheiro garante a instalação do ambiente Python 
# ignorando as restrições de sistema (PEP 668).

echo "🚀 Iniciando Build do Rotagas..."

# 1. Atualizar o instalador de pacotes
python3 -m pip install --upgrade pip

# 2. Instalar dependências do projecto
# A flag --break-system-packages é essencial para o ambiente 'uv' da Vercel
echo "📦 Instalando bibliotecas do requirements.txt..."
python3 -m pip install -r requirements.txt --break-system-packages

# 3. Coletar ficheiros estáticos (CSS, Imagens, JS)
# O WhiteNoise utiliza esta pasta para servir o design do site
echo "🎨 Coletando ficheiros estáticos..."
python3 manage.py collectstatic --noinput --clear

echo "✅ Build finalizado com sucesso!"